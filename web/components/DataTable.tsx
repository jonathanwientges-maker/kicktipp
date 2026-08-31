"use client";
// The one responsive table used across the site (BRIEF §2).
//
// Desktop (>=768px): renders every column, exactly as the old hand-rolled
// tables did. No sticky columns — on horizontal scroll everything moves.
//
// Mobile (<768px):
//   • a full-width segmented control swaps which metric columns render;
//     the identifier column (position + team chip) is always present
//   • tapping a row expands it in place into a key/value card showing
//     EVERY column for that row — this is what guarantees the column-set
//     toggle drops no information
//   • a right-edge fade + a one-line scroll hint appear only while a table
//     still overflows and has not been scrolled
//
// Adds a small amount of client JS; no external dependencies.
import { useCallback, useEffect, useRef, useState } from "react";

export type Col<Row> = {
  key: string;
  /** header label; also the label shown in the expanded card */
  label: string;
  /** cell contents */
  render: (row: Row) => React.ReactNode;
  /** right-aligned tabular number cell */
  numeric?: boolean;
  /** exclude from the expanded card (e.g. a pure "open report" link column) */
  hideInCard?: boolean;
};

export type ColumnSet = {
  label: string;
  /** keys from `columns` (identifier column excluded — it is always shown) */
  keys: string[];
};

export function DataTable<Row extends { id: string | number }>({
  columns,
  rows,
  columnSets,
  /** the always-present leading cell(s): position number + team chip etc.
      `identifierHeader` is its <th> label(s). Provide the same number of
      <th> and <td> so colSpans line up. */
  identifierHeader,
  renderIdentifier,
  identifierColSpan = 2,
  /** optional per-row attributes for the <tr> (e.g. data-zone) */
  rowProps,
  caption,
}: {
  columns: Col<Row>[];
  rows: Row[];
  columnSets: ColumnSet[];
  identifierHeader: React.ReactNode;
  renderIdentifier: (row: Row) => React.ReactNode;
  identifierColSpan?: number;
  rowProps?: (row: Row) => Record<string, string | undefined>;
  caption?: string;
}) {
  const [setIdx, setSetIdx] = useState(0);
  const [openId, setOpenId] = useState<string | number | null>(null);
  const [overflow, setOverflow] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [atEnd, setAtEnd] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeKeys = new Set(columnSets[setIdx]?.keys ?? columns.map((c) => c.key));
  const mobileCols = columns.filter((c) => activeKeys.has(c.key));

  const measure = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const over = el.scrollWidth - el.clientWidth > 1;
    setOverflow(over);
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    measure();
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      setScrolled(true);
      measure();
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      el.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", measure);
    };
  }, [measure, setIdx]);

  const showFade = overflow && !atEnd;
  const showHint = overflow && !scrolled;

  return (
    <div className="dt">
      {columnSets.length > 1 && (
        <div className="dt-seg" role="tablist" aria-label="Spaltenauswahl">
          {columnSets.map((s, i) => (
            <button
              key={s.label}
              role="tab"
              aria-selected={i === setIdx}
              className="dt-seg-btn"
              data-active={i === setIdx}
              onClick={() => {
                setSetIdx(i);
                setOpenId(null);
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {showHint && (
        <div className="dt-hint" aria-hidden="true">
          ← seitlich scrollen für mehr →
        </div>
      )}

      <div className="surface table-scroll dt-scroll" ref={scrollRef}>
        {showFade && <span className="dt-fade" aria-hidden="true" />}
        <table>
          {caption && <caption className="dt-caption">{caption}</caption>}
          <thead>
            {/* desktop header — all columns */}
            <tr className="dt-row-desktop">
              {identifierHeader}
              {columns.map((c) => (
                <th key={c.key} className={c.numeric ? "num" : undefined}>
                  {c.label}
                </th>
              ))}
            </tr>
            {/* mobile header — identifier + active set */}
            <tr className="dt-row-mobile">
              {identifierHeader}
              {mobileCols.map((c) => (
                <th key={c.key} className={c.numeric ? "num" : undefined}>
                  {c.label}
                </th>
              ))}
              <th aria-hidden="true" className="dt-chevcol" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const extra = rowProps?.(row) ?? {};
              const isOpen = openId === row.id;
              return (
                <FragmentRow
                  key={row.id}
                  row={row}
                  columns={columns}
                  mobileCols={mobileCols}
                  renderIdentifier={renderIdentifier}
                  identifierColSpan={identifierColSpan}
                  extra={extra}
                  isOpen={isOpen}
                  onToggle={() => setOpenId(isOpen ? null : row.id)}
                />
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FragmentRow<Row extends { id: string | number }>({
  row,
  columns,
  mobileCols,
  renderIdentifier,
  identifierColSpan,
  extra,
  isOpen,
  onToggle,
}: {
  row: Row;
  columns: Col<Row>[];
  mobileCols: Col<Row>[];
  renderIdentifier: (row: Row) => React.ReactNode;
  identifierColSpan: number;
  extra: Record<string, string | undefined>;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const cardCols = columns.filter((c) => !c.hideInCard);
  const mobileSpan = identifierColSpan + mobileCols.length + 1;
  const { className: extraClass, ...extraAttrs } = extra;

  return (
    <>
      {/* desktop row — all columns, not interactive */}
      <tr {...extraAttrs} className={`dt-row-desktop ${extraClass ?? ""}`}>
        {renderIdentifier(row)}
        {columns.map((c) => (
          <td key={c.key} className={c.numeric ? "num" : undefined}>
            {c.render(row)}
          </td>
        ))}
      </tr>

      {/* mobile row — identifier + active set + chevron; tap toggles card */}
      <tr
        {...extraAttrs}
        className={`dt-row-mobile dt-tappable ${extraClass ?? ""}`}
        data-open={isOpen}
      >
        {renderIdentifier(row)}
        {mobileCols.map((c) => (
          <td key={c.key} className={c.numeric ? "num" : undefined}>
            {c.render(row)}
          </td>
        ))}
        <td className="dt-chevcol">
          <button
            type="button"
            className="dt-chev"
            aria-expanded={isOpen}
            aria-label={isOpen ? "Zeile einklappen" : "Alle Werte anzeigen"}
            onClick={onToggle}
          >
            <span className="dt-chev-icon" data-open={isOpen} aria-hidden="true">
              ›
            </span>
          </button>
        </td>
      </tr>

      {/* mobile expanded card */}
      {isOpen && (
        <tr className="dt-row-mobile dt-cardrow">
          <td colSpan={mobileSpan}>
            <dl className="dt-card">
              {cardCols.map((c) => (
                <div key={c.key} className="dt-card-pair">
                  <dt className="label">{c.label}</dt>
                  <dd className="num">{c.render(row)}</dd>
                </div>
              ))}
            </dl>
          </td>
        </tr>
      )}
    </>
  );
}
