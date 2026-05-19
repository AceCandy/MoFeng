import {
  CategoryScale,
  Chart,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Title,
  Tooltip,
} from 'chart.js'

// 仅注册当前情感折线图必需模块，避免把所有 Chart.js 控件都打进同一个 chunk。
Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, Title)

export { Chart }
