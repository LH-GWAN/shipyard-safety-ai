import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { NaturalLanguagePanel } from "@/features/work-items/NaturalLanguagePanel";
import { makeWorkItem, zones } from "./fixtures";

const apiMock = vi.hoisted(() => ({ parseDescription: vi.fn(), createWorkItem: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: apiMock };
});

const parseResult = {
  draft: {
    values: {
      title: "A_BLOCK_1에서 보강재 용접",
      work_type: "HOT_WORK" as const,
      zone_id: "A_BLOCK_1",
      start_at: "2026-03-16T09:00:00+09:00",
      end_at: "2026-03-16T12:00:00+09:00",
      uses_flammable_material: null,
      gas_measurement_completed: null,
      ventilation_confirmed: null,
      watcher_assigned: null,
    },
    field_confidence: { work_type: 0.9, zone_id: 0.9, title: 0.4 },
    evidence: { work_type: "용접", zone_id: "A_BLOCK_1" },
    ambiguities: [],
    missing_fields: ["uses_flammable_material"],
    provider: "mock",
  },
  llm_enabled: false,
  provider: "mock",
  is_mock: true,
  notice: "키워드 인식 방식(모의 어댑터)으로 읽은 결과입니다. 더 자세한 결과를 얻으려면 LLM API 키가 필요합니다.",
};

describe("자연어 입력 패널", () => {
  it("구조화 결과와 근거·신뢰도를 보여주고 즉시 저장하지 않는다", async () => {
    apiMock.parseDescription.mockResolvedValue(parseResult);
    render(<NaturalLanguagePanel zones={zones} />);

    await userEvent.type(screen.getByLabelText("작업설명 원문"), "2026-03-16T09:00:00+09:00 A_BLOCK_1 용접");
    await userEvent.click(screen.getByRole("button", { name: "구조화 요청" }));

    expect(await screen.findByText(/모의 어댑터/)).toBeInTheDocument();
    expect(screen.getAllByText("0.90").length).toBe(2);
    expect(screen.getAllByText("용접").length).toBeGreaterThan(0);
    expect(apiMock.createWorkItem).not.toHaveBeenCalled();
  });

  it("사용자가 값을 수정한 뒤 저장하면 source_type=LLM으로 등록한다", async () => {
    apiMock.parseDescription.mockResolvedValue(parseResult);
    apiMock.createWorkItem.mockResolvedValue(makeWorkItem({ id: "W900" }));
    render(<NaturalLanguagePanel zones={zones} />);

    await userEvent.type(screen.getByLabelText("작업설명 원문"), "A_BLOCK_1 용접");
    await userEvent.click(screen.getByRole("button", { name: "구조화 요청" }));

    const titleInput = await screen.findByLabelText(/작업명/);
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "수정된 용접 작업");
    await userEvent.click(screen.getByRole("button", { name: "확인 후 저장" }));

    expect(await screen.findByText(/작업계획 W900을\(를\) 저장했습니다./)).toBeInTheDocument();
    expect(apiMock.createWorkItem).toHaveBeenCalledWith(
      expect.objectContaining({ title: "수정된 용접 작업", source_type: "LLM", zone_id: "A_BLOCK_1" }),
    );
  });

  it("LLM 공급자를 사용할 수 없으면 오류 코드를 표시한다", async () => {
    const { ApiError } = await import("@/lib/api");
    apiMock.parseDescription.mockRejectedValue(
      new ApiError("LLM_UNAVAILABLE", "LLM 공급자를 사용할 수 없습니다.", 503),
    );
    render(<NaturalLanguagePanel zones={zones} />);

    await userEvent.type(screen.getByLabelText("작업설명 원문"), "용접 작업");
    await userEvent.click(screen.getByRole("button", { name: "구조화 요청" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("LLM_UNAVAILABLE");
  });
});
