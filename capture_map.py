import carla
import pygame
import numpy as np
import time

def main():
    pygame.init()
    
    # 连接到CARLA
    client = carla.Client('localhost', 2000)
    client.set_timeout(20.0)
    
    # 加载Town03地图
    world = client.load_world('Town03')
    time.sleep(2.0)
    
    # 设置天气为晴天
    weather = carla.WeatherParameters(
        cloudiness=0.0,
        precipitation=0.0,
        sun_altitude_angle=90.0
    )
    world.set_weather(weather)
    
    # 获取观察者
    spectator = world.get_spectator()
    
    # 计算地图中心点和高度
    spawn_points = world.get_map().get_spawn_points()
    if len(spawn_points) > 0:
        locations = [p.location for p in spawn_points]
        x_coords = [l.x for l in locations]
        y_coords = [l.y for l in locations]
        center_x = (max(x_coords) + min(x_coords)) / 2
        center_y = (max(y_coords) + min(y_coords)) / 2
        height = 500.0  # 调整高度以获得合适的视野
    else:
        center_x = 0
        center_y = 0
        height = 500.0
    
    # 设置观察者位置
    spectator.set_transform(carla.Transform(
        carla.Location(x=center_x, y=center_y, z=height),
        carla.Rotation(pitch=-90.0, yaw=0.0, roll=0.0)
    ))
    
    # 创建相机
    camera_bp = world.get_blueprint_library().find('sensor.camera.rgb')
    camera_bp.set_attribute('image_size_x', '1280')
    camera_bp.set_attribute('image_size_y', '720')
    camera_bp.set_attribute('fov', '90')
    
    # 在观察者位置创建相机
    camera = world.spawn_actor(
        camera_bp,
        carla.Transform(
            carla.Location(x=center_x, y=center_y, z=height),
            carla.Rotation(pitch=-90.0, yaw=0.0, roll=0.0)
        )
    )
    
    try:
        # 设置pygame显示
        display = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption('Map Capture')
        
        # 创建一个同步队列来存储图像
        image_queue = []
        
        def camera_callback(image):
            array = np.frombuffer(image.raw_data, dtype=np.dtype("uint8"))
            array = np.reshape(array, (image.height, image.width, 4))
            array = array[:, :, :3]
            array = array[:, :, ::-1]
            image_queue.append(array)
        
        camera.listen(camera_callback)
        
        # 等待并保存图像
        print("Waiting for image...")
        while len(image_queue) == 0:
            time.sleep(0.1)
        
        image = image_queue[0]
        pygame.image.save(pygame.surfarray.make_surface(image), "town03.jpg")
        print("Map image saved as town03.jpg")
        
    finally:
        camera.destroy()
        pygame.quit()

if __name__ == '__main__':
    main()
