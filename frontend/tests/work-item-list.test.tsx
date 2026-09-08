import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkItemListView } from "@/features/work-items/WorkItemListView";
import { makeWorkItem, zones } from "./fixtures";

const apiMock = vi.hoisted(() => ({
  listWorkItems: vi.fn(),
  listZones: vi.fn(),
  deleteWorkItem: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: apiMock };
});

function page(items = [makeWorkItem()]) {
  return { items, total: items.length, page: 1, page_size: 20 };
}

describe("작업 목록 화면", () => {
  it("목록을 불러와 표시한다", async () => {
    apiMock.listZones.mockResolvedValue({ items: zones, total: zones.length });
    apiMock.listWorkItems.mockResolvedValue(page());

    render(<WorkItemListView />);

    expect(screen.getByRole("status")).toHaveTextContent("작업 목록을 불러오는 중입니다.");
    expect(await screen.findByText("A블록 1구역 보강재 용접")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "경보 있음" })).toBeInTheDocument();
  });

  it("필터를 적용하고 초기화할 수 있다", async () => {
    apiMock.listZones.mockResolvedValue({ items: zones, total: zones.length });
    apiMock.listWorkItems.mockResolvedValue(page());

    render(<WorkItemListView />);
    await screen.findByText("A블록 1구역 보강재 용접");

    await userEvent.selectOptions(screen.getByLabelText("작업 종류"), "HOT_WORK");
    await userEvent.selectOptions(screen.getByLabelText("경보 여부"), "true");
    await userEvent.click(screen.getByRole("button", { name: "필터 적용" }));

    await waitFor(() =>
      expect(apiMock.listWorkItems).toHaveBeenLastCalledWith(
        expect.objectContaining({ work_type: "HOT_WORK", has_alert: true, page: 1 }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "필터 초기화" }));

    await waitFor(() =>
      expect(apiMock.listWorkItems).toHaveBeenLastCalledWith(
        expect.objectContaining({ work_type: null, has_alert: null, date: null }),
      ),
    );
  });

  it("결과가 없으면 빈 목록 안내를 보여준다", async () => {
    apiMock.listZones.mockResolvedValue({ items: zones, total: zones.length });
    apiMock.listWorkItems.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });

    render(<WorkItemListView />);

    expect(await screen.findByText("표시할 작업계획이 없습니다.")).toBeInTheDocument();
  });

  it("API 오류를 오류 코드와 함께 표시한다", async () => {
    const { ApiError } = await import("@/lib/api");
    apiMock.listZones.mockResolvedValue({ items: zones, total: zones.length });
    apiMock.listWorkItems.mockRejectedValue(new ApiError("NETWORK_ERROR", "백엔드 API에 연결할 수 없습니다.", 0));

    render(<WorkItemListView />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("백엔드 API에 연결할 수 없습니다.");
    expect(alert).toHaveTextContent("NETWORK_ERROR");
  });

  it("삭제 후 목록을 다시 불러온다", async () => {
    apiMock.listZones.mockResolvedValue({ items: zones, total: zones.length });
    apiMock.listWorkItems.mockResolvedValue(page());
    apiMock.deleteWorkItem.mockResolvedValue(undefined);

    render(<WorkItemListView />);
    await screen.findByText("A블록 1구역 보강재 용접");

    await userEvent.click(screen.getByRole("button", { name: "삭제" }));

    await waitFor(() => expect(apiMock.deleteWorkItem).toHaveBeenCalledWith("W001"));
    expect(apiMock.listWorkItems).toHaveBeenCalledTimes(2);
  });
});
