#!/usr/bin/env python

import carla
import pygame
import json
import random
import time
import datetime
import math
import numpy as np
import os
from rl_agent import RLAgent  # 导入RL代理

class AutonomousScenario:
    def __init__(self):
        # 初始化Carla客户端
        self.client = carla.Client('localhost', 2000)
        self.client.set_timeout(10.0)
        
        # 加载生成点
        with open('spawn_points.json', 'r') as f:
            self.spawn_data = json.load(f)
        
        # 确保加载正确的地图
        world = self.client.get_world()
        if world.get_map().name != self.spawn_data['map_name']:
            self.client.load_world(self.spawn_data['map_name'])
            world = self.client.get_world()
        
        self.world = world
        self.map = world.get_map()  # 获取地图引用
        self.blueprint_library = world.get_blueprint_library()
        
        # 获取TrafficManager并设置全局参数
        self.traffic_manager = self.client.get_trafficmanager(8000)
        self.traffic_manager.set_global_distance_to_leading_vehicle(0.5)
        self.traffic_manager.global_percentage_speed_difference(-30)
        
        # 初始化Pygame
        pygame.init()
        
        # 获取显示器信息
        display_info = pygame.display.Info()
        max_width = min(1600, display_info.current_w - 100)
        max_height = min(900, display_info.current_h - 100)
        
        # 计算主视图尺寸（16:9）
        main_width = max_width - 300
        main_height = int(main_width * 9/16)
        if main_height > max_height:
            main_height = max_height
            main_width = int(main_height * 16/9)
        
        self.display_size = (main_width + 300, main_height)
        self.main_view_size = (main_width, main_height)
        self.side_panel_width = 300
        self.map_size = 280
        
        self.screen = pygame.display.set_mode(self.display_size)
        pygame.display.set_caption('Autonomous Driving Scenario')
        
        # 记录开始时间
        self.start_time = time.time()
        self.round_time = 30
        self.max_rounds = 10
        self.current_round = 0
        
        # 存储车辆和摄像头
        self.ego_vehicle = None
        self.npc_vehicles = []
        self.cameras = {}
        self.camera_surfaces = {}
        
        # 强化学习相关
        self.rl_control = True  # 默认使用RL控制
        self.rl_agent = RLAgent()  # 创建RL代理
        self.last_observation = None
        self.last_action = None
        self.episode_reward = 0
        self.collision_sensor = None
        self.last_collision_time = 0
        self.collision_cooldown = 1.0  # 碰撞检测冷却时间（秒）
        
        # 创建输出文件夹
        self.output_dir = f"scenario_output_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 字体初始化
        self.font_large = pygame.font.Font(None, 48)
        self.font_normal = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)

    def setup_ego_vehicle(self):
        """设置主车"""
        try:
            # 生成主车
            blueprint = self.blueprint_library.find('vehicle.tesla.model3')
            blueprint.set_attribute('role_name', 'ego')
            ego_spawn = self.spawn_data['ego_point']
            transform = carla.Transform(
                carla.Location(x=ego_spawn['x'], y=ego_spawn['y'], z=ego_spawn['z']),
                carla.Rotation(yaw=ego_spawn['yaw'])
            )
            
            # 尝试多次生成主车
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    self.ego_vehicle = self.world.spawn_actor(blueprint, transform)
                    break
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise Exception(f"无法生成主车: {str(e)}")
                    time.sleep(0.5)
            
            # 设置碰撞检测器
            collision_bp = self.blueprint_library.find('sensor.other.collision')
            self.collision_sensor = self.world.spawn_actor(collision_bp, carla.Transform(), attach_to=self.ego_vehicle)
            self.collision_sensor.listen(lambda event: self._on_collision(event))
            
            # 根据控制模式设置车辆
            if not self.rl_control:
                self.ego_vehicle.set_autopilot(True)
            
            # 设置摄像头
            self.setup_cameras()
            
            # 重置RL状态
            self.last_observation = None
            self.last_action = None
            self.episode_reward = 0
            
        except Exception as e:
            print(f"设置主车时出错: {str(e)}")
            raise

    def _on_collision(self, event):
        """碰撞事件处理"""
        current_time = time.time()
        if current_time - self.last_collision_time > self.collision_cooldown:
            self.last_collision_time = current_time
            if self.rl_control and self.last_observation is not None:
                # 给予碰撞惩罚
                reward = self.rl_agent.calculate_reward(
                    self.last_observation, 
                    collision=True
                )
                self.episode_reward += reward
                
                # 存储经验
                current_observation = self.get_observation()
                self.rl_agent.store_experience(
                    self.last_observation,
                    self.last_action,
                    reward,
                    current_observation,
                    True  # 碰撞视为终止状态
                )
                
                # 训练网络
                self.rl_agent.train()

    def update_rl_control(self):
        """更新强化学习控制"""
        if not self.rl_control or not self.ego_vehicle:
            return
            
        try:
            # 获取当前观察
            current_observation = self.get_observation()
            
            if self.last_observation is not None and self.last_action is not None:
                # 计算奖励
                reward = self.rl_agent.calculate_reward(
                    current_observation,
                    collision=False,
                    off_road=not self.ego_vehicle.get_location().z > 0
                )
                self.episode_reward += reward
                
                # 存储经验
                self.rl_agent.store_experience(
                    self.last_observation,
                    self.last_action,
                    reward,
                    current_observation,
                    False
                )
                
                # 训练网络
                self.rl_agent.train()
            
            # 选择动作
            action = self.rl_agent.select_action(current_observation)
            
            # 应用动作
            self.apply_rl_action(action)
            
            # 更新状态
            self.last_observation = current_observation
            self.last_action = action
            
        except Exception as e:
            print(f"更新RL控制时出错: {str(e)}")

    def run(self):
        """运行场景"""
        try:
            # 初始设置
            try:
                self.setup_ego_vehicle()
                time.sleep(0.2)
                self.setup_npc_vehicles()
                time.sleep(0.2)
                print(f"开始第{self.current_round + 1}轮...")
            except Exception as e:
                print(f"初始设置时出错: {str(e)}")
                return
            
            clock = pygame.time.Clock()
            running = True
            
            while running:
                try:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                        elif event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_ESCAPE:
                                running = False
                            elif event.key == pygame.K_SPACE:
                                # 切换控制模式
                                self.rl_control = not self.rl_control
                                if self.ego_vehicle:
                                    self.ego_vehicle.set_autopilot(not self.rl_control)
                                print(f"切换到{'强化学习' if self.rl_control else '自动驾驶'}控制模式")
                    
                    # 更新RL控制
                    if self.rl_control:
                        self.update_rl_control()
                    
                    # 检查是否需要重置场景
                    if time.time() - self.start_time >= self.round_time:
                        # 保存当前轮次的模型
                        if self.rl_control:
                            self.rl_agent.training_history['episode_rewards'].append(self.episode_reward)
                            self.rl_agent.training_history['episode_lengths'].append(self.round_time)
                            self.rl_agent.save_model(self.current_round)
                        
                        if not self.reset_scenario():
                            time.sleep(3)
                            running = False
                    
                    self.draw()
                    clock.tick(60)
                except Exception as e:
                    print(f"主循环中出错: {str(e)}")
                    running = False
        
        finally:
            # 清理资源
            try:
                pygame.quit()
                
                if self.collision_sensor:
                    self.collision_sensor.destroy()
                
                if self.ego_vehicle:
                    self.ego_vehicle.set_autopilot(False)
                    self.ego_vehicle.destroy()
                
                for camera in self.cameras.values():
                    if camera is not None:
                        camera.stop()
                        camera.destroy()
                
                for vehicle in self.npc_vehicles:
                    if vehicle is not None:
                        vehicle.set_autopilot(False)
                        vehicle.destroy()
            except Exception as e:
                print(f"清理资源时出错: {str(e)}")

    def reset_scenario(self):
        """重置场景"""
        print(f"\n正在重置场景... 第{self.current_round + 1}轮完成")
        
        try:
            # 先清理摄像头
            for camera in self.cameras.values():
                if camera is not None:
                    camera.stop()
                    camera.destroy()
            self.cameras.clear()
            self.camera_surfaces.clear()
            time.sleep(0.5)  # 等待摄像头完全清理
            
            # 清理车辆
            if self.ego_vehicle:
                self.ego_vehicle.set_autopilot(False)
                self.ego_vehicle.destroy()
                self.ego_vehicle = None
            
            for vehicle in self.npc_vehicles:
                if vehicle is not None:
                    vehicle.set_autopilot(False)
                    vehicle.destroy()
            self.npc_vehicles.clear()
            
            time.sleep(0.5)  # 等待车辆完全清理
            
            self.current_round += 1
            if self.current_round < self.max_rounds:
                print(f"开始第{self.current_round + 1}轮...")
                try:
                    # 重新设置场景
                    self.setup_ego_vehicle()
                    time.sleep(0.2)  # 等待主车生成
                    self.setup_npc_vehicles()
                    time.sleep(0.2)  # 等待NPC生成
                    self.start_time = time.time()
                    return True
                except Exception as e:
                    print(f"重置场景时出错: {str(e)}")
                    return False
            else:
                print("所有轮次已完成！")
                return False
        except Exception as e:
            print(f"清理场景时出错: {str(e)}")
            return False

    def draw(self):
        """绘制pygame界面"""
        if 'main' not in self.camera_surfaces or 'map' not in self.camera_surfaces:
            return
            
        # 填充黑色背景
        self.screen.fill((0, 0, 0))
        
        # 主视角（左侧）
        self.screen.blit(self.camera_surfaces['main'], (0, 0))
        
        # 右侧信息面板背景
        side_panel = pygame.Surface((self.side_panel_width, self.display_size[1]))
        side_panel.fill((20, 20, 20))  # 深灰色背景
        self.screen.blit(side_panel, (self.main_view_size[0], 0))
        
        # 小地图（右上）
        map_pos = (self.main_view_size[0] + 10, 10)  # 留出边距
        map_bg = pygame.Surface((self.map_size, self.map_size))
        map_bg.fill((0, 0, 0))
        self.screen.blit(map_bg, map_pos)
        self.screen.blit(self.camera_surfaces['map'], map_pos)
        
        # 显示NPC数量
        npc_text = f"NPCs: {len(self.npc_vehicles)}"
        npc_surface = self.font_normal.render(npc_text, True, (200, 200, 200))
        self.screen.blit(npc_surface, (map_pos[0], map_pos[1] + self.map_size + 10))
        
        # 获取并显示车辆数据
        vehicle_info = self.get_vehicle_data()
        self.draw_vehicle_info(vehicle_info, self.main_view_size[0] + 10, self.map_size + 80)
        
        # 显示当前轮次和时间
        time_left = self.round_time - (time.time() - self.start_time) % self.round_time
        
        # 在主屏幕左上方显示轮次信息
        info_bg = pygame.Surface((300, 100))
        info_bg.fill((0, 0, 0))
        info_bg.set_alpha(160)
        self.screen.blit(info_bg, (20, 20))
        
        round_text = f"Round {self.current_round + 1}/{self.max_rounds}"
        time_text = f"Time: {int(time_left)}s"
        
        round_surface = self.font_large.render(round_text, True, (255, 255, 255))
        time_surface = self.font_large.render(time_text, True, (255, 255, 255))
        
        self.screen.blit(round_surface, (30, 30))
        self.screen.blit(time_surface, (30, 70))
        
        # 底部操作提示
        help_text = "ESC: Exit | Space: Switch Mode | Right Click: Save"
        help_surface = self.font_small.render(help_text, True, (200, 200, 200))
        help_bg = pygame.Surface((help_surface.get_width() + 20, help_surface.get_height() + 10))
        help_bg.fill((0, 0, 0))
        help_bg.set_alpha(160)
        
        help_pos = (self.display_size[0] - help_surface.get_width() - 30, self.display_size[1] - 40)
        self.screen.blit(help_bg, (help_pos[0] - 10, help_pos[1] - 5))
        self.screen.blit(help_surface, help_pos)
        
        pygame.display.flip()

    def get_vehicle_data(self):
        """获取车辆数据"""
        if not self.ego_vehicle:
            return None
            
        velocity = self.ego_vehicle.get_velocity()
        transform = self.ego_vehicle.get_transform()
        control = self.ego_vehicle.get_control()
        
        # 计算速度
        speed = 3.6 * math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)  # km/h
        
        return {
            'speed': speed,
            'heading': transform.rotation.yaw,
            'location': transform.location,
            'throttle': control.throttle,
            'brake': control.brake,
            'steer': control.steer,
            'gear': control.gear
        }

    def draw_vehicle_info(self, info, start_x, start_y):
        """绘制车辆信息仪表盘"""
        if not info:
            return
            
        # 背景面板
        panel_width = self.side_panel_width - 20  # 留出边距
        panel_height = 280
        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.fill((0, 0, 0))
        panel_surface.set_alpha(160)  # 稍微透明一些
        self.screen.blit(panel_surface, (start_x, start_y))
        
        y_offset = start_y + 20
        x_padding = start_x + 20
        
        # 速度表（大字体）
        speed_text = f"{info['speed']:.1f} km/h"
        speed_surface = self.font_large.render(speed_text, True, (255, 255, 255))
        self.screen.blit(speed_surface, (x_padding, y_offset))
        
        y_offset += 60
        
        # 方向盘状态
        steer_text = f"Steering: {info['steer']:.2f}"
        steer_surface = self.font_normal.render(steer_text, True, (255, 255, 255))
        self.screen.blit(steer_surface, (x_padding, y_offset))
        
        y_offset += 40
        
        # 油门刹车
        throttle_text = f"Throttle: {info['throttle']:.2f}"
        brake_text = f"Brake: {info['brake']:.2f}"
        throttle_surface = self.font_normal.render(throttle_text, True, (0, 255, 0))
        brake_surface = self.font_normal.render(brake_text, True, (255, 0, 0))
        self.screen.blit(throttle_surface, (x_padding, y_offset))
        self.screen.blit(brake_surface, (x_padding, y_offset + 40))
        
        y_offset += 80
        
        # 档位
        gear_text = f"Gear: {info['gear']}"
        gear_surface = self.font_normal.render(gear_text, True, (255, 255, 255))
        self.screen.blit(gear_surface, (x_padding, y_offset))
        
        y_offset += 40
        
        # 坐标
        loc = info['location']
        loc_text = f"Location: ({loc.x:.1f}, {loc.y:.1f})"
        loc_surface = self.font_small.render(loc_text, True, (200, 200, 200))
        self.screen.blit(loc_surface, (x_padding, y_offset))

    def get_observation(self):
        """获取当前状态观察"""
        if not self.ego_vehicle:
            return None
            
        try:
            # 基本车辆状态
            velocity = self.ego_vehicle.get_velocity()
            accel = self.ego_vehicle.get_acceleration()
            angular_velocity = self.ego_vehicle.get_angular_velocity()
            transform = self.ego_vehicle.get_transform()
            control = self.ego_vehicle.get_control()
            
            # 获取车辆物理状态
            physics_control = self.ego_vehicle.get_physics_control()
            wheels = physics_control.wheels
            wheel_positions = np.array([[wheel.position.x, wheel.position.y, wheel.position.z] for wheel in wheels])
            
            # 获取车道信息
            waypoint = self.map.get_waypoint(self.ego_vehicle.get_location())
            next_waypoints = []
            current_waypoint = waypoint
            for _ in range(10):  # 获取前方10个路点
                next_waypoint = current_waypoint.next(5.0)[0]  # 每5米一个点
                next_waypoints.append([
                    next_waypoint.transform.location.x,
                    next_waypoint.transform.location.y,
                    next_waypoint.transform.location.z,
                    next_waypoint.transform.rotation.yaw
                ])
                current_waypoint = next_waypoint
            
            # 获取车道线信息
            left_lane = waypoint.get_left_lane()
            right_lane = waypoint.get_right_lane()
            lane_width = waypoint.lane_width
            lane_change = waypoint.lane_change
            
            # 获取交通信号和标志
            lights_list = self.world.get_actors().filter('traffic.traffic_light')
            signs_list = self.world.get_actors().filter('traffic.traffic_sign')
            
            # 处理最近的交通信号
            closest_light = None
            min_light_distance = float('inf')
            light_state = -1  # -1表示无信号灯
            
            for light in lights_list:
                light_location = light.get_location()
                distance = light_location.distance(self.ego_vehicle.get_location())
                if distance < min_light_distance and distance < 50.0:  # 50米内的信号灯
                    min_light_distance = distance
                    closest_light = light
                    light_state = light.get_state().value
            
            # 获取天气信息
            weather = self.world.get_weather()
            
            # 构建观察字典
            observation = {
                # 基本运动学信息
                'velocity': np.array([velocity.x, velocity.y, velocity.z], dtype=np.float32),
                'acceleration': np.array([accel.x, accel.y, accel.z], dtype=np.float32),
                'angular_velocity': np.array([
                    angular_velocity.x, angular_velocity.y, angular_velocity.z
                ], dtype=np.float32),
                
                # 位置和方向
                'location': np.array([
                    transform.location.x, transform.location.y, transform.location.z
                ], dtype=np.float32),
                'rotation': np.array([
                    transform.rotation.pitch, transform.rotation.yaw, transform.rotation.roll
                ], dtype=np.float32),
                
                # 控制状态
                'control_state': np.array([
                    control.throttle, control.steer, control.brake,
                    float(control.hand_brake), float(control.reverse)
                ], dtype=np.float32),
                
                # 车轮状态
                'wheel_positions': wheel_positions.astype(np.float32),
                
                # 车道信息
                'lane_info': np.array([
                    lane_width,
                    float(waypoint.is_junction),
                    float(waypoint.is_intersection),
                    float(lane_change == carla.LaneChange.Left),
                    float(lane_change == carla.LaneChange.Right),
                    float(lane_change == carla.LaneChange.Both),
                    float(left_lane is not None),
                    float(right_lane is not None)
                ], dtype=np.float32),
                
                # 路径信息
                'waypoints': np.array(next_waypoints, dtype=np.float32),
                
                # 周围车辆信息
                'nearest_vehicles': self._get_nearby_vehicle_distances(),
                'vehicle_info': self._get_nearby_vehicle_info(),
                
                # 交通信号
                'traffic_light': np.array([
                    min_light_distance if closest_light else 100.0,
                    light_state
                ], dtype=np.float32),
                
                # 天气信息
                'weather': np.array([
                    weather.cloudiness,
                    weather.precipitation,
                    weather.precipitation_deposits,
                    weather.wind_intensity,
                    weather.fog_density,
                    weather.wetness
                ], dtype=np.float32),
                
                # 碰撞和危险信息
                'danger_info': self._get_danger_info()
            }
            
            return observation
            
        except Exception as e:
            print(f"获取观察时出错: {str(e)}")
            return None

    def _get_nearby_vehicle_info(self):
        """获取周围车辆的详细信息"""
        vehicle_info = np.zeros((8, 4), dtype=np.float32)  # 8个方向，每个方向4个值
        if not self.ego_vehicle:
            return vehicle_info
            
        ego_location = self.ego_vehicle.get_location()
        ego_transform = self.ego_vehicle.get_transform()
        ego_forward = ego_transform.get_forward_vector()
        ego_velocity = self.ego_vehicle.get_velocity()
        
        # 获取所有车辆
        vehicles = self.world.get_actors().filter('vehicle.*')
        for vehicle in vehicles:
            if vehicle.id == self.ego_vehicle.id:
                continue
                
            # 计算相对位置
            relative_location = vehicle.get_location() - ego_location
            distance = relative_location.length()
            if distance > 100.0:  # 忽略100米外的车辆
                continue
            
            # 计算相对速度
            vehicle_velocity = vehicle.get_velocity()
            relative_velocity = math.sqrt(
                (vehicle_velocity.x - ego_velocity.x) ** 2 +
                (vehicle_velocity.y - ego_velocity.y) ** 2 +
                (vehicle_velocity.z - ego_velocity.z) ** 2
            )
            
            # 计算角度
            angle = math.degrees(math.atan2(relative_location.y, relative_location.x))
            angle = (angle - math.degrees(math.atan2(ego_forward.y, ego_forward.x))) % 360
            
            # 确定方向扇区（8个45度扇区）
            sector = int((angle + 22.5) / 45) % 8
            
            # 计算时间to collision (TTC)
            if relative_velocity > 0:
                ttc = distance / relative_velocity
            else:
                ttc = 100.0  # 默认安全值
            
            # 如果这个扇区还没有车辆，或者这个车辆更近，则更新信息
            if vehicle_info[sector][0] == 0 or distance < vehicle_info[sector][0]:
                vehicle_info[sector] = np.array([
                    distance,
                    relative_velocity,
                    ttc,
                    angle
                ], dtype=np.float32)
        
        return vehicle_info

    def _get_danger_info(self):
        """获取危险相关的信息"""
        if not self.ego_vehicle:
            return np.zeros(5, dtype=np.float32)
            
        try:
            location = self.ego_vehicle.get_location()
            velocity = self.ego_vehicle.get_velocity()
            speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
            
            # 获取当前车道
            waypoint = self.map.get_waypoint(location)
            
            # 计算车道偏离
            lane_center = waypoint.transform.location
            lane_deviation = math.sqrt(
                (location.x - lane_center.x)**2 +
                (location.y - lane_center.y)**2
            )
            
            # 计算与路缘的距离
            lane_width = waypoint.lane_width
            distance_to_edge = (lane_width / 2) - lane_deviation
            
            # 获取道路曲率
            next_waypoint = waypoint.next(2.0)[0]
            road_curvature = abs(
                math.degrees(math.atan2(
                    next_waypoint.transform.location.y - waypoint.transform.location.y,
                    next_waypoint.transform.location.x - waypoint.transform.location.x
                ))
            )
            
            # 计算当前加速度
            acceleration = self.ego_vehicle.get_acceleration()
            accel_magnitude = math.sqrt(
                acceleration.x**2 + acceleration.y**2 + acceleration.z**2
            )
            
            return np.array([
                lane_deviation,        # 车道偏离程度
                distance_to_edge,      # 到路缘距离
                road_curvature,        # 道路曲率
                speed,                 # 当前速度
                accel_magnitude        # 加速度大小
            ], dtype=np.float32)
            
        except Exception as e:
            print(f"获取危险信息时出错: {str(e)}")
            return np.zeros(5, dtype=np.float32)

if __name__ == '__main__':
    try:
        scenario = AutonomousScenario()
        scenario.run()
    except KeyboardInterrupt:
        print("Scenario interrupted by user")
    except Exception as e:
        print(f"Error occurred: {e}")
