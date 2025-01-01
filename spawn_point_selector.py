#!/usr/bin/env python

import carla
import pygame
import json
import sys
import os
import math

class SpawnPointSelector:
    def __init__(self):
        # 初始化Carla客户端
        self.client = carla.Client('localhost', 2000)
        self.client.set_timeout(4.0)
        
        # 加载指定地图
        self.client.load_world('Town03')
        self.world = self.client.get_world()
        self.map = self.world.get_map()
        
        # 获取官方生成点和路网点
        self.spawn_points = self.map.get_spawn_points()
        self.waypoints = self.map.generate_waypoints(2.0)
        
        # 计算地图边界
        self.calculate_map_bounds()
        
        # 初始化Pygame
        pygame.init()
        self.width = 1280
        self.height = 960
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption('Carla Spawn Point Selector - Space to switch mode')
        
        # 计算合适的缩放比例
        self.calculate_scale()
        
        # 存储选择的点
        self.ego_point = None  # 主车只能有一个点
        self.npc_points = []   # NPC可以有多个点
        self.selecting_ego = True
        
        # 加载已有的生成点
        self.spawn_points_file = 'spawn_points.json'
        self.load_spawn_points()

    def load_spawn_points(self):
        if os.path.exists(self.spawn_points_file):
            try:
                with open(self.spawn_points_file, 'r') as f:
                    data = json.load(f)
                    self.ego_point = data.get('ego_point')
                    self.npc_points = data.get('npc_points', [])
            except:
                print("无法加载已有生成点文件")

    def save_spawn_points(self):
        data = {
            'ego_point': self.ego_point,
            'npc_points': self.npc_points,
            'map_name': self.map.name
        }
        with open(self.spawn_points_file, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"生成点已保存到 {self.spawn_points_file}")

    def calculate_map_bounds(self):
        """计算地图边界"""
        # 同时考虑路网点和生成点来计算边界
        x_coords = ([wp.transform.location.x for wp in self.waypoints] + 
                   [sp.location.x for sp in self.spawn_points])
        y_coords = ([wp.transform.location.y for wp in self.waypoints] +
                   [sp.location.y for sp in self.spawn_points])
        
        # 扩大边界确保显示完整
        margin = 50  # 米
        self.map_bounds = {
            'min_x': min(x_coords) - margin,
            'max_x': max(x_coords) + margin,
            'min_y': min(y_coords) - margin,
            'max_y': max(y_coords) + margin
        }
        
    def calculate_scale(self):
        """计算合适的缩放比例"""
        map_width = self.map_bounds['max_x'] - self.map_bounds['min_x']
        map_height = self.map_bounds['max_y'] - self.map_bounds['min_y']
        
        # 留出一些边距
        margin = 0.1
        width_scale = (self.width * (1 - margin)) / map_width
        height_scale = (self.height * (1 - margin)) / map_height
        
        # 使用较小的缩放比例以确保地图完全显示
        self.scale = min(width_scale, height_scale)

    def world_to_screen(self, location):
        """将世界坐标转换为屏幕坐标"""
        center_x = (self.map_bounds['min_x'] + self.map_bounds['max_x']) / 2
        center_y = (self.map_bounds['min_y'] + self.map_bounds['max_y']) / 2
        
        # 转换坐标
        screen_x = self.width/2 + (location.x - center_x) * self.scale
        screen_y = self.height/2 - (location.y - center_y) * self.scale
        return (int(screen_x), int(screen_y))

    def screen_to_world(self, screen_pos):
        """将屏幕坐标转换为世界坐标"""
        center_x = (self.map_bounds['min_x'] + self.map_bounds['max_x']) / 2
        center_y = (self.map_bounds['min_y'] + self.map_bounds['max_y']) / 2
        
        x = center_x + (screen_pos[0] - self.width/2) / self.scale
        y = center_y - (screen_pos[1] - self.height/2) / self.scale
        return carla.Location(x=x, y=y, z=0.0)

    def draw(self):
        self.screen.fill((0, 0, 0))  # 黑色背景
        
        # 绘制背景路网点（灰色小点）
        for wp in self.waypoints:
            pos = self.world_to_screen(wp.transform.location)
            pygame.draw.circle(self.screen, (50, 50, 50), pos, 1)
        
        # 绘制官方生成点和方向（白色）
        for spawn_point in self.spawn_points:
            pos = self.world_to_screen(spawn_point.location)
            direction_length = 20
            angle = math.radians(spawn_point.rotation.yaw)
            end_pos = (
                pos[0] + direction_length * math.cos(angle),
                pos[1] - direction_length * math.sin(angle)
            )
            pygame.draw.circle(self.screen, (200, 200, 200), pos, 4)
            pygame.draw.line(self.screen, (200, 200, 200), pos, end_pos, 2)
        
        # 绘制主车生成点（红色）
        if self.ego_point:
            loc = carla.Location(x=self.ego_point['x'], y=self.ego_point['y'], z=self.ego_point['z'])
            pos = self.world_to_screen(loc)
            angle = math.radians(self.ego_point.get('yaw', 0))
            end_pos = (
                pos[0] + direction_length * math.cos(angle),
                pos[1] - direction_length * math.sin(angle)
            )
            pygame.draw.circle(self.screen, (255, 0, 0), pos, 6)
            pygame.draw.line(self.screen, (255, 0, 0), pos, end_pos, 2)
        
        # 绘制NPC生成点（蓝色）
        for point in self.npc_points:
            loc = carla.Location(x=point['x'], y=point['y'], z=point['z'])
            pos = self.world_to_screen(loc)
            angle = math.radians(point.get('yaw', 0))
            end_pos = (
                pos[0] + direction_length * math.cos(angle),
                pos[1] - direction_length * math.sin(angle)
            )
            pygame.draw.circle(self.screen, (0, 0, 255), pos, 6)
            pygame.draw.line(self.screen, (0, 0, 255), pos, end_pos, 2)
        
        # 显示当前模式和计数
        font = pygame.font.Font(None, 36)
        mode_text = "Current Mode: EGO Vehicle (Only one)" if self.selecting_ego else f"Current Mode: NPC Vehicle ({len(self.npc_points)})"
        text_surface = font.render(mode_text, True, (255, 255, 255))
        self.screen.blit(text_surface, (10, 10))
        
        # 显示图例
        legend_font = pygame.font.Font(None, 28)
        legend_y = 50
        legend_spacing = 25
        
        # 白色点说明
        white_text = "White Points: Available Spawn Points"
        white_surface = legend_font.render(white_text, True, (200, 200, 200))
        self.screen.blit(white_surface, (10, legend_y))
        
        # 红色点说明
        red_text = "Red Point: Selected EGO Vehicle (Click again to remove)"
        red_surface = legend_font.render(red_text, True, (255, 0, 0))
        self.screen.blit(red_surface, (10, legend_y + legend_spacing))
        
        # 蓝色点说明
        blue_text = "Blue Points: Selected NPC Vehicles (Click to remove)"
        blue_surface = legend_font.render(blue_text, True, (0, 0, 255))
        self.screen.blit(blue_surface, (10, legend_y + legend_spacing * 2))
        
        # 箭头说明
        arrow_text = "Arrow: Vehicle Forward Direction"
        arrow_surface = legend_font.render(arrow_text, True, (200, 200, 200))
        self.screen.blit(arrow_surface, (10, legend_y + legend_spacing * 3))
        
        # 显示地图名称
        map_text = f"Current Map: {self.map.name}"
        map_surface = legend_font.render(map_text, True, (200, 200, 200))
        self.screen.blit(map_surface, (10, legend_y + legend_spacing * 4))
        
        # 显示操作说明
        help_text = "Left Click: Select/Remove Spawn Point | Right Click: Save | Space: Switch Mode | ESC: Exit"
        help_surface = font.render(help_text, True, (200, 200, 200))
        self.screen.blit(help_surface, (10, self.height - 30))
        
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左键点击
                        world_pos = self.screen_to_world(event.pos)
                        # 获取最近的官方生成点
                        closest_point = min(self.spawn_points, 
                                         key=lambda sp: math.sqrt(
                                             (sp.location.x - world_pos.x)**2 + 
                                             (sp.location.y - world_pos.y)**2))
                        point = {
                            'x': closest_point.location.x,
                            'y': closest_point.location.y,
                            'z': closest_point.location.z,
                            'yaw': closest_point.rotation.yaw
                        }
                        
                        if self.selecting_ego:
                            # 如果点击的是当前主车点位置，则移除它
                            if (self.ego_point and 
                                abs(self.ego_point['x'] - point['x']) < 0.1 and 
                                abs(self.ego_point['y'] - point['y']) < 0.1):
                                self.ego_point = None
                            else:
                                self.ego_point = point
                        else:
                            # 如果点击的是已有的NPC点，则移除它
                            remove_idx = None
                            for i, npc_point in enumerate(self.npc_points):
                                if (abs(npc_point['x'] - point['x']) < 0.1 and 
                                    abs(npc_point['y'] - point['y']) < 0.1):
                                    remove_idx = i
                                    break
                            if remove_idx is not None:
                                self.npc_points.pop(remove_idx)
                            else:
                                self.npc_points.append(point)
                    
                    elif event.button == 3:  # 右键点击
                        self.save_spawn_points()
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.selecting_ego = not self.selecting_ego
                    elif event.key == pygame.K_ESCAPE:
                        running = False
            
            self.draw()
        
        pygame.quit()

if __name__ == '__main__':
    try:
        selector = SpawnPointSelector()
        selector.run()
    except KeyboardInterrupt:
        print('\n退出程序')
    except Exception as e:
        print('发生错误:', e)
