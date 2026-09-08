import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CsvUploadPanel } from "@/features/work-items/CsvUploadPanel";
import type { CsvImportResult } from "@/types/domain";

const apiMock = vi.hoisted(() => ({ importCsv: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: apiMock };
});

const validateResult: CsvImportResult = {
  total_rows: 2,
  valid_count: 1,
  invalid_count: 1,
  created_count: 0,
  updated_count: 0,
  committed: false,
  valid_rows: [
    {
      row_number: 2,
      work_item: {
        id: "W001",
        title: "보강재 용접",
        description: null,
        work_type: "HOT_WORK",
        zone_id: "A_BLOCK_1",
        start_at: "2026-03-16T09:00:00+09:00",
        end_at: "2026-03-16T12:00:00+09:00",
        uses_flammable_material: null,
        gas_measurement_completed: null,
        ventilation_confirmed: null,
        watcher_assigned: null,
        status: "DRAFT",
      },
    },
  ],
  errors: [
    {
      row_number: 3,
      field: "work_type",
      code: "INVALID_CSV_VALUE",
      message: "허용되지 않는 값입니다. 허용값: HOT_WORK, PAINTING, SOLVENT_WORK, CONFINED_SPACE, OTHER",
      raw_value: "hot_work",
    },
  ],
};

function csvFile() {
  return new File(["id,title\n"], "work_items.csv", { type: "text/csv" });
}

describe("CSV 업로드 패널", () => {
  it("검증만 실행하면 행별 오류와 미저장 안내를 보여준다", async () => {
    apiMock.importCsv.mockResolvedValue(validateResult);
    render(<CsvUploadPanel />);

    await userEvent.upload(screen.getByLabelText("CSV 파일"), csvFile());
    await userEvent.click(screen.getByRole("button", { name: "검증만 실행" }));

    expect(await screen.findByText(/행별 오류 \(1건\)/)).toBeInTheDocument();
    expect(screen.getByText("INVALID_CSV_VALUE")).toBeInTheDocument();
    expect(screen.getByText("hot_work")).toBeInTheDocument();
    expect(screen.getByText(/데이터베이스는 변경되지 않았습니다/)).toBeInTheDocument();
    expect(apiMock.importCsv).toHaveBeenCalledWith(expect.any(File), { commit: false, overwrite: false });
  });

  it("유효 행 저장을 누르면 commit=true로 요청하고 저장 결과를 알린다", async () => {
    apiMock.importCsv.mockResolvedValueOnce(validateResult).mockResolvedValueOnce({
      ...validateResult,
      created_count: 1,
      committed: true,
    });
    const onSaved = vi.fn();
    render(<CsvUploadPanel onSaved={onSaved} />);

    await userEvent.upload(screen.getByLabelText("CSV 파일"), csvFile());
    await userEvent.click(screen.getByRole("button", { name: "검증만 실행" }));
    await userEvent.click(await screen.findByRole("button", { name: "유효 행 저장" }));

    expect(await screen.findByText(/유효한 1개 행을 저장했습니다/)).toBeInTheDocument();
    expect(apiMock.importCsv).toHaveBeenLastCalledWith(expect.any(File), { commit: true, overwrite: false });
    expect(onSaved).toHaveBeenCalled();
  });

  it("업로드 제한 초과 같은 API 오류를 코드와 함께 표시한다", async () => {
    const { ApiError } = await import("@/lib/api");
    apiMock.importCsv.mockRejectedValue(
      new ApiError("CSV_LIMIT_EXCEEDED", "CSV 행 수가 제한(1000행)을 초과했습니다.", 413),
    );
    render(<CsvUploadPanel />);

    await userEvent.upload(screen.getByLabelText("CSV 파일"), csvFile());
    await userEvent.click(screen.getByRole("button", { name: "검증만 실행" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("CSV 행 수가 제한(1000행)을 초과했습니다.");
    expect(alert).toHaveTextContent("CSV_LIMIT_EXCEEDED");
  });
});
