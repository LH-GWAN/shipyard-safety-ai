import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkItemForm } from "@/features/work-items/WorkItemForm";
import { zones } from "./fixtures";

describe("작업 직접 등록 폼", () => {
  it("필수 항목이 비면 저장하지 않고 필드 오류를 보여준다", async () => {
    const onSubmit = vi.fn();
    render(<WorkItemForm zones={zones} submitLabel="작업계획 저장" onSubmit={onSubmit} />);

    await userEvent.click(screen.getByRole("button", { name: "작업계획 저장" }));

    expect(await screen.findByText("작업명을 입력하십시오.")).toBeInTheDocument();
    expect(screen.getByText("시작시각을 입력하십시오.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("종료시각이 시작시각보다 빠르면 오류를 보여준다", async () => {
    const onSubmit = vi.fn();
    render(<WorkItemForm zones={zones} submitLabel="저장" onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText(/작업명/), "테스트 용접");
    await userEvent.type(screen.getByLabelText(/시작시각/), "2026-03-16T12:00");
    await userEvent.type(screen.getByLabelText(/종료시각/), "2026-03-16T09:00");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));

    expect(await screen.findByText("종료시각은 시작시각보다 늦어야 합니다.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("유효한 값은 KST 오프셋을 포함한 ISO 문자열로 전달한다", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<WorkItemForm zones={zones} allowIdInput submitLabel="저장" onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText(/작업 ID/), "T100");
    await userEvent.type(screen.getByLabelText(/작업명/), "  테스트 용접  ");
    await userEvent.selectOptions(screen.getByLabelText(/작업 종류/), "HOT_WORK");
    await userEvent.selectOptions(screen.getByLabelText(/^구역/), "A_BLOCK_1");
    await userEvent.type(screen.getByLabelText(/시작시각/), "2026-03-16T09:00");
    await userEvent.type(screen.getByLabelText(/종료시각/), "2026-03-16T12:00");
    await userEvent.selectOptions(screen.getByLabelText("가스측정 완료"), "false");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      id: "T100",
      title: "테스트 용접",
      work_type: "HOT_WORK",
      zone_id: "A_BLOCK_1",
      start_at: "2026-03-16T09:00:00+09:00",
      end_at: "2026-03-16T12:00:00+09:00",
      gas_measurement_completed: false,
      ventilation_confirmed: null,
    });
  });

  it("서버 오류 메시지와 오류 코드를 표시한다", async () => {
    const { ApiError } = await import("@/lib/api");
    const onSubmit = vi.fn().mockRejectedValue(new ApiError("DUPLICATE_WORK_ITEM_ID", "이미 존재하는 작업 ID입니다.", 409));
    render(<WorkItemForm zones={zones} submitLabel="저장" onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText(/작업명/), "중복 작업");
    await userEvent.type(screen.getByLabelText(/시작시각/), "2026-03-16T09:00");
    await userEvent.type(screen.getByLabelText(/종료시각/), "2026-03-16T12:00");
    await userEvent.click(screen.getByRole("button", { name: "저장" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("이미 존재하는 작업 ID입니다.");
    expect(screen.getByRole("alert")).toHaveTextContent("DUPLICATE_WORK_ITEM_ID");
  });
});
