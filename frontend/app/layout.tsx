import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "YardGuard",
  description: "조선소 작업계획 사전 검토 보조 도구",
};

const NAV = [
  { href: "/", label: "대시보드" },
  { href: "/work-items", label: "작업 목록" },
  { href: "/work-items/new", label: "작업 등록" },
  { href: "/analysis", label: "분석 결과" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen">
        <header className="border-b border-slate-300 bg-white">
          <div className="mx-auto flex max-w-[1280px] items-center justify-between gap-6 px-6 py-3">
            <div>
              <p className="text-lg font-bold text-slate-900">YardGuard</p>
              <p className="text-xs text-slate-600">조선소 작업계획 사전 검토 보조 도구 (합성 데이터 기반)</p>
            </div>
            <nav aria-label="주요 메뉴">
              <ul className="flex gap-1 text-sm">
                {NAV.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="rounded px-3 py-2 text-slate-700 hover:bg-slate-100 hover:text-slate-900"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-[1280px] px-6 py-6">{children}</main>
        <footer className="mx-auto max-w-[1280px] px-6 pb-8 text-xs text-slate-500">
          YardGuard는 작업허가 승인, 법적 적합성 판정, 작업중지 명령이나 설비 제어 기능을 제공하지 않습니다.
        </footer>
      </body>
    </html>
  );
}
