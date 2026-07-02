import React, { useMemo, useState } from 'react';

export default function ItemList({
  title,
  items,
  selected,
  onToggle,
  onSelectAll,
  onClear,
  getKey,
  renderRow,
  loading,
  onRefresh,
  emptyHint,
}) {
  const [filter, setFilter] = useState('');
  const filtered = useMemo(() => {
    if (!filter) return items;
    const q = filter.toLowerCase();
    return items.filter((i) => JSON.stringify(i).toLowerCase().includes(q));
  }, [items, filter]);

  const allSelected =
    filtered.length > 0 && filtered.every((i) => selected.has(getKey(i)));

  return (
    <div className="card">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center gap-3">
        <h3 className="font-semibold text-slate-800">{title}</h3>
        <span className="badge bg-slate-100 text-slate-600">
          {items.length}
        </span>
        <div className="flex-1" />
        <input
          className="input max-w-xs"
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button className="btn-secondary" onClick={onRefresh} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      <div className="px-5 py-2 border-b border-slate-100 flex items-center gap-3 text-sm">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={(e) =>
              e.target.checked
                ? onSelectAll(filtered.map(getKey))
                : onClear(filtered.map(getKey))
            }
          />
          <span className="text-slate-600">
            Select all {filter ? 'filtered' : ''}
          </span>
        </label>
        <span className="text-slate-400">
          {selected.size} selected
        </span>
      </div>
      <div className="max-h-96 overflow-y-auto divide-y divide-slate-100">
        {filtered.length === 0 && (
          <div className="p-8 text-center text-slate-500 text-sm">
            {loading ? 'Loading…' : emptyHint || 'No items'}
          </div>
        )}
        {filtered.map((item) => {
          const key = getKey(item);
          const isSelected = selected.has(key);
          return (
            <label
              key={key}
              className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50 cursor-pointer"
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => onToggle(key)}
              />
              {renderRow(item)}
            </label>
          );
        })}
      </div>
    </div>
  );
}
