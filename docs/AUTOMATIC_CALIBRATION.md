# 自动标定操作与结果解释

## 1. 准备

- 相机以 USB 3 连接，关闭占用相机的 Viewer 或其他采集程序。
- 将完整 ChArUco 棋盘贴在平整、刚性的表面，避免反光、弯曲、遮挡。
- 对照配置中的 5 × 7 方格、`DICT_5X5_100` 字典；完整板共 17 个 marker、24 个内角点。
- 实测方格和 marker 外侧黑色边框边长，更新 board YAML 中的 measured 字段。
  仓库当前记录的 24 mm / 12 mm 只适用于对应打印件，不应直接套用到另一张纸。
- 标称图案生成尺寸是 25 mm / 12.5 mm；打印缩放后的实测值与其可能不同。

## 2. 先检查，再多视角采集

`inspect` 只读取工厂参数、检测棋盘、估计板位姿并生成单视角深度诊断。
该模式不会重新求解内参。使用 `--confirm-board-size` 表示已核对当前打印件实测尺寸；
未确认时报告中的米制位姿标为 provisional。

`auto` 自动检测、过滤模糊/移动中画面和重复视角、保存采集记录并求解彩色相机内参。
建议 25 个或更多视角，每次停稳约 2 秒，覆盖：

1. 中心与图像四周；尽量让完整棋盘入镜。
2. 近、中、远距离，仍需清晰分辨小 marker。
3. 绕水平和垂直轴倾斜；只平移正对镜头的棋盘不足以约束所有参数。

没有机械执行器时，程序不负责移动相机或棋盘。静止运行通常只保存一个视角，
结束状态为 `needs_more_views`，不生成内参结果。每次运行使用独立目录，不混入历史图片。
保存的 `capture.json` 记录每个视图的角点数量、清晰度、归一化四顶点位置及时间。

## 3. 解释结果

- `T_color_from_board` 满足 `p_color = R @ p_board + t`，平移单位为米；
  板原点及轴采用 OpenCV ChArUco board 定义，彩色相机坐标为 x 向右、y 向下、z 向前。
- 位姿使用工厂彩色内参。非零畸变仅接受标准 Brown–Conrady；其他模型明确跳过位姿，
  不把 RealSense inverse/modified 系数直接当作 OpenCV 系数。零畸变系数不受该差异影响。
- `aligned_depth.npy` 是 SDK 对齐至彩色网格后的原始深度；乘 `factory.json` 的 depth scale 得到米。
- 角点附近 5 × 5 深度有效像素中位数与 PnP 预测 Z 的差，仅是局部一致性诊断；
  不单独代表深度精度、对齐精度或长度测量准确度。全为零的深度没有有效统计值。
- `color_intrinsics.json` 中训练 RMS 和留出视角 RMS 均以像素计。
  留出图片未参与内参拟合，但其位姿仍通过这些图片拟合，非独立米制真值验证。
- 最终状态 `calibration_candidate_needs_validation` 明确表示候选结果。
  使用前应检查残差、视角分布、参数合理性，并与相同条件下的工厂参数比较。
- 新内参只适用于相同分辨率和成像配置。SDK 的 `rs.align` 仍使用设备工厂参数；
  单独替换彩色 K 并不会更新 SDK 对齐，也不会校准深度模块。

## 4. 本地结果与 GitHub

代码、配置、生成图案、文档和合成测试可以发布。
`outputs/sessions/`、其他采集输出以及实机序列号保持本地，不随 Git 提交。
测试用程序合成的棋盘，不上传办公室画面。

Windows 下请从已激活的 Conda 环境或通过 `conda run` 执行。
直接调用某个环境里的 `python.exe` 而未激活，可能缺少本机数值库所需的 DLL 搜索路径。

## 参考

- [OpenCV ChArUco calibration: multiple viewpoints](https://docs.opencv.org/4.5.0/da/d13/tutorial_aruco_calibration.html)
- [RealSense projection and distortion models](https://github.com/realsenseai/librealsense/wiki/Projection-in-RealSense-SDK-2.0)
