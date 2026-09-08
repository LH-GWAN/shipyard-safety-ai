import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DashboardView } from "@/features/dashboard/DashboardView";
import { makeAnalysis, makeWorkItem } from "./fixtures";

const apiMock = vi.hoisted(() => ({
  listWorkItems: vi.fn(),
  latestAnalysis: vi.fn(),
  health: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: apiMock };
});

describe("대시보드", () => {
  it("요약 지표와 제한 문구를 보여준다", async () => {
    apiMock.listWorkItems.mockResolvedValue({
      items: [makeWorkItem(), makeWorkItem({ id: "W002", status: "DRAFT" })],
      total: 2,
      page: 1,
      page_size: 100,
    });
    apiMock.latestAnalysis.mockResolvedValue(makeAnalysis());
    apiMock.health.mockResolvedValue({ status: "ok", llm_enabled: true, llm_provider: "anthropic", zone_count: 12 });

    render(<DashboardView />);

    const totalCard = (await screen.findByText("전체 작업 수")).closest("div")!;
    expect(within(totalCard).getByText("2건")).toBeInTheDocument();
    const unreviewedCard = screen.getByText("미검토 작업").closest("div")!;
    expect(within(unreviewedCard).getByText("1건")).toBeInTheDocument();
    expect(screen.getByText("등급 높음 경보")).toBeInTheDocument();
    expect(screen.getByText("미검토 작업")).toBeInTheDocument();
    expect(screen.getByTestId("disclaimer")).toBeInTheDocument();
    expect(screen.queryByText(/키워드 인식 방식\(모의 어댑터\)/)).not.toBeInTheDocument();
  });

  it("LLM 비활성 상태를 안내한다", async () => {
    apiMock.listWorkItems.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 });
    apiMock.latestAnalysis.mockResolvedValue(null);
    apiMock.health.mockResolvedValue({ status: "ok", llm_enabled: false, llm_provider: "mock", zone_count: 12 });

    render(<DashboardView />);

    expect(await screen.findByText(/키워드 인식 방식\(모의 어댑터\)으로 동작합니다/)).toBeInTheDocument();
    expect(screen.getByText(/LLM API 키가/)).toBeInTheDocument();
    expect(screen.getByText("분석 이력 없음")).toBeInTheDocument();
    expect(screen.getByText(/등록된 작업계획이 없습니다/)).toBeInTheDocument();
  });

  it("로딩 상태와 API 오류 상태를 각각 보여준다", async () => {
    const { ApiError } = await import("@/lib/api");
    apiMock.listWorkItems.mockRejectedValue(new ApiError("NETWORK_ERROR", "백엔드 API에 연결할 수 없습니다.", 0));
    apiMock.latestAnalysis.mockResolvedValue(null);
    apiMock.health.mockResolvedValue({ status: "ok", llm_enabled: false, llm_provider: "mock", zone_count: 12 });

    render(<DashboardView />);

    expect(screen.getByRole("status")).toHaveTextContent("대시보드를 불러오는 중입니다.");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("백엔드 API에 연결할 수 없습니다.");
    expect(alert).toHaveTextContent("NETWORK_ERROR");
  });
});
