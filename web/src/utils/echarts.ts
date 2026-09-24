/**
 * ECharts 按需注册（避免打包整个 echarts 库）
 * 仅注册工作台用到的组件：柱状图 / 散点图 / 自定义系列（甘特图）+ 基础组件
 */
import * as echarts from "echarts/core";
import { BarChart, CustomChart, ScatterChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  BarChart,
  LineChart,
  ScatterChart,
  CustomChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  LegendComponent,
  CanvasRenderer,
]);

export default echarts;
