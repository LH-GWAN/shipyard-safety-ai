import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ScheduleShiftPanel } from "@/features/analysis/ScheduleShiftPanel";
import { confinedAlert, makeAnalysis, pairAlert } from "./fixtures";

const apiMock = vi.hoisted(() => ({ previewShift: vi.fn(), applyShift: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: apiMock };
});

const preview = {
  preview_token: "token-abc",
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
  remaining_alert_count: 0,
  before_alert_count: 1,
  after_alert_count: 0,
};

describe("일정 변경 패널의 사용자 확인 절차", () => {
  it("미리보기 전에는 적용 버튼이 없고 확인 안내를 보여준다", () => {
    render(<ScheduleShiftPanel alert={pairAlert} onApplied={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "변경안 적용" })).not.toBeInTheDocument();
    expect(screen.getByText(/변경안을 미리보기로 확인한 뒤에만 적용할 수 있습니다/)).toBeInTheDocument();
  });

  it("적용 요청에는 항상 미리보기 토큰이 포함된다", async () => {
    apiMock.previewShift.mockResolvedValue(preview);
    apiMock.applyShift.mockResolvedValue({
      change: preview.change,
      analysis: makeAnalysis({ alert_count: 0, alerts: [] }),
      resolved_alerts: [pairAlert],
      new_alerts: [],
    });
    render(<ScheduleShiftPanel alert={pairAlert} onApplied={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "변경안 미리보기" }));
    await userEvent.click(await screen.findByRole("button", { name: "변경안 적용" }));

    await waitFor(() => expect(apiMock.applyShift).toHaveBeenCalledTimes(1));
    expect(apiMock.applyShift).toHaveBeenCalledWith({
      alert_id: pairAlert.id,
      move_work_item_id: "W002",
      buffer_minutes: 30,
      preview_token: "token-abc",
    });
  });

  it("이동 작업을 바꾸면 미리보기 결과와 토큰을 폐기한다", async () => {
    apiMock.previewShift.mockResolvedValue(preview);
    render(<ScheduleShiftPanel alert={pairAlert} onApplied={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "변경안 미리보기" }));
    expect(await screen.findByRole("button", { name: "변경안 적용" })).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("이동할 작업"), "W001");

    expect(screen.queryByRole("button", { name: "변경안 적용" })).not.toBeInTheDocument();
    expect(apiMock.applyShift).not.toHaveBeenCalled();
  });

  it("여유시간을 바꾸면 미리보기 결과와 토큰을 폐기한다", async () => {
    apiMock.previewShift.mockResolvedValue(preview);
    render(<ScheduleShiftPanel alert={pairAlert} onApplied={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "변경안 미리보기" }));
    expect(await screen.findByRole("button", { name: "변경안 적용" })).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText(/여유시간/), "0");

    expect(screen.queryByRole("button", { name: "변경안 적용" })).not.toBeInTheDocument();
  });

  it("취소를 누르면 미리보기 결과를 폐기한다", async () => {
    apiMock.previewShift.mockResolvedValue(preview);
    render(<ScheduleShiftPanel alert={pairAlert} onApplied={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "변경안 미리보기" }));
    await userEvent.click(await screen.findByRole("button", { name: "취소" }));

    expect(screen.queryByRole("button", { name: "변경안 적용" })).not.toBeInTheDocument();
    expect(apiMock.applyShift).not.toHaveBeenCalled();
  });

  it("단일 작업 경보에는 변경안 UI를 제공하지 않는다", () => {
    render(<ScheduleShiftPanel alert={confinedAlert} onApplied={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "변경안 미리보기" })).not.toBeInTheDocument();
    expect(screen.getByText(/두 작업의 시간이 겹친 경보에만 제공됩니다/)).toBeInTheDocument();
  });
});

describe("API 클라이언트의 토큰 방어", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("토큰이 비어 있으면 네트워크 요청을 보내지 않고 오류를 던진다", async () => {
    const { api, ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    const fetchSpy = vi.fn();
    global.fetch = fetchSpy as unknown as typeof fetch;

    expect(() =>
      api.applyShift({
        alert_id: "AL_x",
        move_work_item_id: "W002",
        buffer_minutes: 30,
        preview_token: "",
      }),
    ).toThrowError(ApiError);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("토큰이 있으면 적용 요청을 전송한다", async () => {
    const { api } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    const fetchSpy = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      text: async () => JSON.stringify({ change: {}, analysis: {}, resolved_alerts: [], new_alerts: [] }),
    });
    global.fetch = fetchSpy as unknown as typeof fetch;

    await api.applyShift({
      alert_id: "AL_x",
      move_work_item_id: "W002",
      buffer_minutes: 30,
      preview_token: "token-abc",
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0];
    expect(JSON.parse(init.body as string).preview_token).toBe("token-abc");
  });
});
