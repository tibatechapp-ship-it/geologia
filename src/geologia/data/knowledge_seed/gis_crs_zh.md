# GIS 与坐标参考系统 — 处理前检查

GEOLOGIA 原创工程清单。坐标值本身不包含 CRS；不能仅凭数字范围猜测坐标系。

## 必须记录
- EPSG 代码或完整 WKT、基准/参考框架、必要时的坐标历元、轴顺序、单位和转换操作。
- 几何类型、空间范围、坐标范围、是否包含高程，以及坐标是角度还是线性单位。
- 文件名、校验和、创建/采集日期和数据来源。

## 安全流程
1. 保留原始文件和元数据。
2. 在计算距离、面积、缓冲区或坡度前检查 CRS 和单位。
3. 根据区域和测量目的选择目标 CRS；确认基准转换和轴顺序。
4. 输出为新的派生数据，不覆盖原坐标。
5. 验证几何、范围、单位和转换记录，并保存软件版本。

## 常见问题
- 把经纬度的度数当成米。
- 混用水平和垂直基准。
- 假定所有 GIS 库使用相同轴顺序。
- 根据猜测的位置或数字范围选择 CRS。
- 在大范围投影中不检查变形就测量距离。

## 参考资料
- QGIS CRS reference: https://www.qgis.org/pyqgis/master/core/QgsCoordinateReferenceSystem.html
- BGS OpenGeoscience API/OGL: https://www.bgs.ac.uk/technologies/web-services/api/
