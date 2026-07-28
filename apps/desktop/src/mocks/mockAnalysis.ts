export type Direction = "偏多" | "中性" | "偏空";

export interface PerspectiveMock {
  readonly id: "wallstreet" | "quant" | "hotmoney" | "fusion";
  readonly label: string;
  readonly direction: Direction;
  readonly directionScore: number;
  readonly confidence: number;
  readonly action: "WATCH" | "NO_TRADE";
  readonly rationale: string;
}

export interface MockAnalysis {
  readonly fixtureKind: "SYNTHETIC_MOCK";
  readonly instrumentId: string;
  readonly symbol: string;
  readonly displayName: string;
  readonly market: "US";
  readonly snapshotId: string;
  readonly asOf: string;
  readonly marketTimezone: "America/New_York";
  readonly requestedHorizon: "5d";
  readonly riskPermission: "PAPER_TRADE_ONLY";
  readonly dataFreshness: "SYNTHETIC_MOCK";
  readonly perspectives: readonly PerspectiveMock[];
}

export const mockAnalysis: MockAnalysis = {
  fixtureKind: "SYNTHETIC_MOCK",
  instrumentId: "00000000-0000-4000-8000-000000000001",
  symbol: "DEMO",
  displayName: "合成科技样本",
  market: "US",
  snapshotId: "10000000-0000-4000-8000-000000000001",
  asOf: "2026-07-24T20:00:00Z",
  marketTimezone: "America/New_York",
  requestedHorizon: "5d",
  riskPermission: "PAPER_TRADE_ONLY",
  dataFreshness: "SYNTHETIC_MOCK",
  perspectives: [
    {
      id: "wallstreet",
      label: "华尔街视角",
      direction: "偏多",
      directionScore: 28,
      confidence: 0.54,
      action: "WATCH",
      rationale: "合成情景：基本面规则略偏正，但没有真实公告或估值数据。",
    },
    {
      id: "quant",
      label: "量化机构视角",
      direction: "中性",
      directionScore: 6,
      confidence: 0.42,
      action: "NO_TRADE",
      rationale: "合成情景：样本量与成本后优势不足，基线选择不交易。",
    },
    {
      id: "hotmoney",
      label: "游资视角",
      direction: "偏空",
      directionScore: -18,
      confidence: 0.48,
      action: "NO_TRADE",
      rationale: "合成情景：主题处于分歧期，量能与 VWAP 确认缺失。",
    },
    {
      id: "fusion",
      label: "融合视角",
      direction: "中性",
      directionScore: 2,
      confidence: 0.39,
      action: "NO_TRADE",
      rationale: "合成情景：模型分歧且数据质量为 Mock，风险层仅允许模拟观察。",
    },
  ],
};
