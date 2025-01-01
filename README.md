# Carla自动驾驶强化学习快速启动小工具

一个帮助新手快速启动Carla自动驾驶的小工具集合，算是我个人学习过程的记录。



## 主要工具

### 1. 初始化工具 (`init_carla_server.py`)
用于启动和配置Carla服务器
使用前先把程序的路径设置为你安装Carla服务器的目录。
```python
carla_path = "G:/Simulator/WindowsNoEditor/CarlaUE4.exe"
```
这样的路径替换为你的Carla服务器路径。


```bash
python init_carla_server.py
```
自动清理服务器进程，避免程序报端口被占用的错误。
自动启动服务器，方便下一步运行你的程序。

### 2. 生成点选择器 (`spawn_point_selector.py`)
交互式工具，用于在地图上选择和保存车辆生成点：
```bash
python spawn_point_selector.py
```
功能：
- 以路网形式可视化地图和可用官方生成点，带车辆方向
- 交互式选择和保存生成点
- 支持主车和NPC场景配置
- 自动保存为JSON格式，例子参考项目下的JSON
#### 使用说明
空格切换主车和NPC点位选择器。

左键选中，双击撤回，右键保存，Esc退出。

```python
self.client.load_world('Town03')
```
这里可以选择你想要的地图，运行程序后服务器会切换到你选择的地图。


### 3. 自动驾驶场景示例 (`autonomous_scenario.py`)
主要的自动驾驶训练场景：
```bash
python autonomous_scenario.py
```
特点：
- 主车和NPC生成点位采用上面生成的JSON文件
- 集成强化学习代理
- 支持多种NPC行为模式
- 丰富的观察空间
- 实时可视化和数据记录
- 支持GPU加速训练



## 快速开始

1. 把几个小工具拖进你的项目目录下。

2. 启动Carla服务器：
```bash
python init_carla_server.py
```

3. 配置生成点：
```bash
python spawn_point_selector.py
```

4. 运行训练场景（仅仅是示例，所以相关的依赖我就不写了）：
```bash
python autonomous_scenario.py
```

## 控制说明

- `ESC`: 退出场景
- `空格`: 切换控制模式（RL/自动驾驶）
- `R`: 重置场景
- `P`: 暂停/继续

## 输出说明

训练过程中会自动生成以下输出：

1. 模型检查点：`scenario_output_[timestamp]/models/`
2. 训练日志：`scenario_output_[timestamp]/logs/`
3. 评估数据：`scenario_output_[timestamp]/eval/`

## 注意事项

1. 确保CUDA和PyTorch版本匹配
2. 运行前检查Carla服务器状态
3. 建议使用独立显卡运行
4. 定期备份训练数据

## 贡献指南

欢迎提交Issue和Pull Request来改进项目。在提交代码前，请确保：

1. 代码符合PEP 8规范
2. 添加适当的注释和文档
3. 通过所有测试用例

## 许可证

本项目采用MIT许可证。详见LICENSE文件。
