import { describe, expect, it } from "vitest";
import { formatDateTime, formatMinutes, toKstIso, toLocalInput } from "@/lib/format";
import { triStateLabel } from "@/lib/labels";

describe("포맷 유틸리티", () => {
  it("datetime-local 입력값에 KST 오프셋을 붙인다", () => {
    expect(toKstIso("2026-03-16T09:00")).toBe("2026-03-16T09:00:00+09:00");
    expect(toKstIso("")).toBe("");
  });

  it("ISO 문자열을 KST 기준 입력값으로 되돌린다", () => {
    expect(toLocalInput("2026-03-16T09:00:00+09:00")).toBe("2026-03-16T09:00");
    expect(toLocalInput("2026-03-16T00:00:00+00:00")).toBe("2026-03-16T09:00");
    expect(toLocalInput(null)).toBe("");
  });

  it("KST 기준으로 날짜시각을 표시한다", () => {
    expect(formatDateTime("2026-03-16T09:00:00+09:00")).toContain("09:00");
    expect(formatDateTime(null)).toBe("-");
  });

  it("분 단위를 사람이 읽는 형태로 표시한다", () => {
    expect(formatMinutes(45)).toBe("45분");
    expect(formatMinutes(60)).toBe("1시간");
    expect(formatMinutes(150)).toBe("2시간 30분");
  });

  it("null과 false를 구분해 표시한다", () => {
    expect(triStateLabel(null)).toBe("미입력");
    expect(triStateLabel(false)).toBe("아니오(미실시)");
    expect(triStateLabel(true)).toBe("예");
  });
});
