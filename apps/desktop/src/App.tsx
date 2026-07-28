import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Flex,
  Progress,
  Space,
  Tag,
  Typography,
  theme,
} from "antd";

import { fetchHealth } from "./api/health";
import { mockAnalysis } from "./mocks/mockAnalysis";
import { useUiStore } from "./state/uiStore";

const { Paragraph, Text, Title } = Typography;

function formatConfidence(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
    style: "percent",
  }).format(value);
}

function connectionLabel(
  status: "pending" | "error" | "success",
  version: string | undefined,
): string {
  if (status === "success") {
    return `后端在线 · v${version ?? "unknown"}`;
  }
  if (status === "pending") {
    return "正在检查本地后端";
  }
  return "后端离线 · 缓存演示";
}

export function App() {
  const themeMode = useUiStore((state) => state.themeMode);
  const toggleTheme = useUiStore((state) => state.toggleTheme);
  const healthQuery = useQuery({
    queryFn: ({ signal }) => fetchHealth(signal),
    queryKey: ["system", "health"],
    refetchInterval: 30_000,
  });
  const connectionStatus = healthQuery.isPending
    ? "pending"
    : healthQuery.isError
      ? "error"
      : "success";

  return (
    <ConfigProvider
      theme={{
        algorithm: themeMode === "dark" ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          borderRadius: 14,
          colorPrimary: "#57d6b4",
          fontFamily: '"Inter", "SF Pro Display", "Segoe UI", "PingFang SC", sans-serif',
        },
      }}
    >
      <main className={`app-shell ${themeMode}`}>
        <header className="topbar">
          <div>
            <Text className="eyebrow">QFUSION DESKTOP · M0</Text>
            <Title level={2}>多视角交易决策工作台</Title>
          </div>
          <Space wrap>
            <Tag
              className="connection-tag"
              color={connectionStatus === "success" ? "success" : "warning"}
            >
              {connectionLabel(connectionStatus, healthQuery.data?.version)}
            </Tag>
            <Button onClick={toggleTheme}>
              {themeMode === "dark" ? "切换浅色" : "切换深色"}
            </Button>
          </Space>
        </header>

        <Alert
          className="mock-alert"
          message="SYNTHETIC_MOCK · 仅用于界面与契约验证"
          description="以下方向、置信度与风险许可都是固定合成数据，不是行情、预测或投资建议。"
          showIcon
          type="warning"
        />

        <section className="hero-grid" aria-label="分析摘要">
          <Card className="instrument-card" variant="borderless">
            <Flex align="flex-start" justify="space-between" gap={16} wrap>
              <div>
                <Text className="eyebrow">
                  {mockAnalysis.market} · {mockAnalysis.symbol}
                </Text>
                <Title level={1}>{mockAnalysis.displayName}</Title>
                <Paragraph>
                  五日观察周期 · 数据截止 {mockAnalysis.asOf} ·{" "}
                  {mockAnalysis.marketTimezone}
                </Paragraph>
              </div>
              <Tag color="gold">{mockAnalysis.fixtureKind}</Tag>
            </Flex>
            <div className="metadata-row">
              <div>
                <Text type="secondary">永久证券 ID</Text>
                <Text code>{mockAnalysis.instrumentId}</Text>
              </div>
              <div>
                <Text type="secondary">共享 Snapshot ID</Text>
                <Text code>{mockAnalysis.snapshotId}</Text>
              </div>
            </div>
          </Card>

          <Card className="permission-card" variant="borderless">
            <Text className="eyebrow">GLOBAL RISK PERMISSION</Text>
            <Title level={3}>{mockAnalysis.riskPermission}</Title>
            <Paragraph>
              数据质量为合成 Mock。风险层不授予实时交易许可，仅允许模拟观察。
            </Paragraph>
            <Tag color="processing">最终动作 · NO_TRADE</Tag>
          </Card>
        </section>

        <section aria-labelledby="perspective-heading">
          <div className="section-heading">
            <div>
              <Text className="eyebrow">3 + 1 INDEPENDENT VIEWS</Text>
              <Title id="perspective-heading" level={3}>
                四视角快照
              </Title>
            </div>
            <Text type="secondary">
              独立模型不读取彼此结论；融合只读取验证后的 Packet
            </Text>
          </div>

          <div className="perspective-grid">
            {mockAnalysis.perspectives.map((perspective) => (
              <Card
                className="perspective-card"
                key={perspective.id}
                variant="borderless"
              >
                <Flex justify="space-between" align="center" gap={12}>
                  <Text strong>{perspective.label}</Text>
                  <Tag
                    color={
                      perspective.directionScore > 10
                        ? "success"
                        : perspective.directionScore < -10
                          ? "error"
                          : "default"
                    }
                  >
                    {perspective.direction}
                  </Tag>
                </Flex>
                <div className="score-line">
                  <span className="score-value">
                    {perspective.directionScore > 0 ? "+" : ""}
                    {perspective.directionScore}
                  </span>
                  <Text type="secondary">方向分数</Text>
                </div>
                <Progress
                  percent={Math.round(perspective.confidence * 100)}
                  showInfo={false}
                  strokeColor="#57d6b4"
                  trailColor="rgba(127, 143, 164, 0.18)"
                />
                <Flex justify="space-between">
                  <Text type="secondary">校准置信度</Text>
                  <Text>{formatConfidence(perspective.confidence)}</Text>
                </Flex>
                <Paragraph className="rationale">{perspective.rationale}</Paragraph>
                <Tag>{perspective.action}</Tag>
              </Card>
            ))}
          </div>
        </section>

        <footer>
          <Text type="secondary">
            M0 基线 · 无真实数据源 · 无 LLM 调用 · 无订单提交 · 缓存优先
          </Text>
        </footer>
      </main>
    </ConfigProvider>
  );
}
