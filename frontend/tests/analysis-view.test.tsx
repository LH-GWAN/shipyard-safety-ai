import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnalysisView } from "@/features/analysis/AnalysisView";
import { confinedAlert, makeAnalysis, makeWorkItem, pairAlert, rules } from "./fixtures";

const apiMock = vi.hoisted(() => ({
  latestAnalysis: vi.fn(),
  listRules: vi.fn(),
  listWorkItems: vi.fn(),
  runAnalysis: vi.fn(),
  previewShift: vi.fn(),
  applyShift: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: apiMock };
});

const workItems = [
  makeWorkItem(),
  makeWorkItem({
    id: "W002",
    title: "A블록 1구역 외판 도장",
    work_type: "PAINTING",
    start_at: "2026-03-16T11:00:00+09:00",
    end_at: "2026-03-16T14:00:00+09:00",
  }),
];

function setup(latest: unknown = null) {
  apiMock.latestAnalysis.mockResolvedValue(latest);
  apiMock.listRules.mockResolvedValue({ items: rules, total: rules.length });
  apiMock.listWorkItems.mockResolvedValue({ items: workItems, total: workItems.length, page: 1, page_size: 100 });
}

const preview = {
  preview_token: "token-1",
  alert_id: pairAlert.id,
  change: {
    work_item_id: "W002",
    title: "A블록 1구역 외판 도장",
    before_start_at: "2026-03-16T11:00:00+09:00",
    before_end_at: "2026-03-16T14:00:00+09:00",
    after_start_at: "2026-03-16T12:30:00+09:00",
    after_end_at: "2026-03-16T15:30:00+09:00",
    duration_minutes: 180,
    buffer_minutes: 30,
    reference_work_item_id: "W001",
  },
  resolved_alerts: [pairAlert],
  new_alerts: [],
  remaining_alert_count: 1,
  before_alert_count: 2,
  after_alert_count: 1,
};

describe("분석 결과 화면", () => {
  it("분석 이력이 없으면 빈 화면 안내를 보여준다", async () => {
    setup(null);
    render(<AnalysisView />);

    expect(await screen.findByText("아직 분석 결과가 없습니다.")).toBeInTheDocument();
    expect(screen.getByTestId("disclaimer")).toHaveTextContent("안전관리자의 최종 확인이 필요합니다");
  });

  it("규칙 검사를 실행하면 요약과 경보 목록을 보여준다", async () => {
    setup(null);
    apiMock.runAnalysis.mockResolvedValue(makeAnalysis());
    render(<AnalysisView />);
    await screen.findByText("아직 분석 결과가 없습니다.");

    await userEvent.click(screen.getByRole("button", { name: "규칙 검사 실행" }));

    expect(await screen.findByText("경보 2건")).toBeInTheDocument();
    expect(screen.getByText(/높음 2 · 보통 0 · 낮음 0/)).toBeInTheDocument();
    expect(apiMock.runAnalysis).toHaveBeenCalledWith({ date: null });
  });

  it("경보 상세에 규칙, 구역 관계, 중첩시간, 근거와 권고사항을 표시한다", async () => {
    setup(makeAnalysis());
    render(<AnalysisView />);

    const detail = await screen.findByRole("region", { name: "경보 상세" });
    expect(within(detail).getByText(/화기작업과 도장작업 충돌/)).toBeInTheDocument();
    expect(within(detail).getByText("동일 구역")).toBeInTheDocument();
    expect(within(detail).getByText(/1시간/)).toBeInTheDocument();
    expect(within(detail).getByText(/두 작업의 시간을 분리하거나/)).toBeInTheDocument();
    expect(within(detail).getAllByText("등급 높음").length).toBeGreaterThan(0);
  });

  it("경보 상세에 검증된 법령 근거와 비판정 고지를 함께 표시한다", async () => {
    setup(makeAnalysis());
    render(<AnalysisView />);

    const detail = await screen.findByRole("region", { name: "경보 상세" });
    expect(within(detail).getByText(/제241조제2항제3호/)).toBeInTheDocument();
    expect(within(detail).getByRole("link", { name: "국가법령정보센터에서 조문 보기" })).toHaveAttribute(
      "href",
      "https://www.law.go.kr/법령/산업안전보건기준에관한규칙",
    );
    expect(within(detail).getByText(/조문 확인일 2026-09-06/)).toBeInTheDocument();
    expect(within(detail).getByText(/법 위반 판정이 아닙니다/)).toBeInTheDocument();
  });

  it("단일 작업 경보에는 시간 변경안을 제공하지 않는다", async () => {
    setup(makeAnalysis());
    render(<AnalysisView />);

    const list = await screen.findByRole("region", { name: "경보 목록" });
    await userEvent.click(within(list).getByText(new RegExp(confinedAlert.rule_id)).closest("button")!);

    const detail = await screen.findByRole("region", { name: "경보 상세" });
    expect(within(detail).getByText(/값 미입력\(null\)/)).toBeInTheDocument();
    expect(screen.getByText(/두 작업의 시간이 겹친 경보에만 제공됩니다/)).toBeInTheDocument();
  });

  it("시간 변경안을 미리 보고 적용하면 전체 재분석 결과를 반영한다", async () => {
    setup(makeAnalysis());
    apiMock.previewShift.mockResolvedValue(preview);
    apiMock.applyShift.mockResolvedValue({
      change: preview.change,
      analysis: makeAnalysis({ analysis_id: "AN_after", alert_count: 1, alerts: [confinedAlert] }),
      resolved_alerts: [pairAlert],
      new_alerts: [],
    });

    render(<AnalysisView />);
    await screen.findByRole("region", { name: "경보 상세" });

    const shiftPanel = screen.getByRole("region", { name: "일정 변경" });
    await userEvent.selectOptions(within(shiftPanel).getByLabelText("이동할 작업"), "W002");
    await userEvent.click(within(shiftPanel).getByRole("button", { name: "변경안 미리보기" }));

    expect(await within(shiftPanel).findByText("변경 전후 비교")).toBeInTheDocument();
    expect(within(shiftPanel).getByText(/해소되는 경보 \(1건\)/)).toBeInTheDocument();
    expect(within(shiftPanel).getByText(/새로 생기는 경보 \(0건\)/)).toBeInTheDocument();
    expect(apiMock.previewShift).toHaveBeenCalledWith({
      alert_id: pairAlert.id,
      move_work_item_id: "W002",
      buffer_minutes: 30,
    });

    await userEvent.click(within(shiftPanel).getByRole("button", { name: "변경안 적용" }));

    await waitFor(() => expect(apiMock.applyShift).toHaveBeenCalledWith(expect.objectContaining({ preview_token: "token-1" })));
    expect(await screen.findByText(/전체 작업을 다시 검사했습니다. 남은 경보 1건/)).toBeInTheDocument();
  });

  it("일정 변경 미리보기가 만료되면 오류 코드를 보여준다", async () => {
    const { ApiError } = await import("@/lib/api");
    setup(makeAnalysis());
    apiMock.previewShift.mockResolvedValue(preview);
    apiMock.applyShift.mockRejectedValue(
      new ApiError("STALE_SCHEDULE_PREVIEW", "미리보기 내용이 더 이상 유효하지 않습니다.", 409),
    );

    render(<AnalysisView />);
    const shiftPanel = await screen.findByRole("region", { name: "일정 변경" });
    await userEvent.click(within(shiftPanel).getByRole("button", { name: "변경안 미리보기" }));
    await userEvent.click(await within(shiftPanel).findByRole("button", { name: "변경안 적용" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("STALE_SCHEDULE_PREVIEW");
  });

  it("등급·규칙 필터를 적용하고 초기화할 수 있다", async () => {
    setup(makeAnalysis());
    render(<AnalysisView />);
    await screen.findByRole("region", { name: "경보 목록" });

    await userEvent.selectOptions(screen.getByLabelText("규칙 필터"), "R101");
    expect(await screen.findByText("경보 1건")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "필터 초기화" }));
    expect(await screen.findByText("경보 2건")).toBeInTheDocument();
  });
});
