# 遥感影像 — 产品准备检查

GEOLOGIA 原创清单。影像文件不一定是经过科学校准的产品。

## 必要元数据
- 传感器/平台、采集日期时间、处理级别、产品 ID 和数据提供方。
- 波段名称/波长、像元大小、辐射比例/偏移、单位，以及数值是 DN、辐亮度、TOA 反射率还是地表反射率。
- CRS、定位质量、场景范围、云/阴影 QA、大气校正和重采样。
- 地面控制点、来源、残差以及独立检查点。

## 预检查
1. 在选择指数或分类方法前读取产品元数据和 QA 波段。
2. 不在缺少协调方法时混合不兼容的传感器、波段、季节或处理级别。
3. 按产品 QA 规则屏蔽云、阴影、饱和和无效像元。
4. 保留原始影像并记录每一步派生操作。
5. 检查影像和辅助图层是否有第三方许可限制。

## 解释边界
遥感可支持制图和变化检测，但单一光谱特征不能证明矿化、地下水或地质单元；需要地面验证和独立审核。

## 参考资料
- NASA Landsat overview: https://science.nasa.gov/mission/landsat/data-overview/
- USGS Landsat rights: https://www.usgs.gov/faqs/are-landsat-data-cloud-still-considered-be-within-public-domain
