import React, { useMemo, useState } from 'react';

const STATUS_COLORS = {
  created: 'bg-green-100 text-green-700',
  updated: 'bg-blue-100 text-blue-700',
  skipped: 'bg-slate-100 text-slate-600',
  failed: 'bg-red-100 text-red-700',
};

const KIND_COLORS = {
  user: 'bg-teal-100 text-teal-700',
  datasource: 'bg-purple-100 text-purple-700',
  folder: 'bg-amber-100 text-amber-700',
  dashboard: 'bg-indigo-100 text-indigo-700',
  alert: 'bg-pink-100 text-pink-700',
  contact_point: 'bg-orange-100 text-orange-700',
  mute_timing: 'bg-yellow-100 text-yellow-700',
  notification_policy: 'bg-cyan-100 text-cyan-700',
};

function KindRow({ label, color, done, total }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  if (total === 0) return null;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          <span className={`badge ${color}`}>{label}</span>
          <span className="text-slate-500 tabular-nums">{done} / {total}</span>
        </div>
        <span className="font-semibold text-slate-800 tabular-nums">{pct}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
        <div
          className="h-full bg-slate-700 transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function ProgressTab({ progress, results, summary }) {
  const total = progress?.totals?.total || 0;
  const done = progress?.done || 0;
  const overallPct = total > 0 ? Math.round((done / total) * 100) : 0;

  const perKindDone = { user: 0, datasource: 0, dashboard: 0, alert: 0, contact_point: 0, notification_policy: 0 };
  (results || []).forEach((r) => {
    if (perKindDone[r.kind] !== undefined) perKindDone[r.kind] += 1;
  });

  return (
    <div className="space-y-6">
      {/* big overall percentage */}
      <div className="flex items-center gap-6">
        <div className="text-6xl font-bold text-brand-600 tabular-nums min-w-[8rem]">
          {overallPct}%
        </div>
        <div className="flex-1 space-y-2">
          <div className="flex justify-between text-sm text-slate-600">
            <span>Overall progress</span>
            <span className="tabular-nums">{done} / {total} items</span>
          </div>
          <div className="h-4 w-full rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full bg-brand-600 transition-all duration-300"
              style={{ width: `${overallPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* per-kind */}
      <div className="space-y-4">
        <KindRow label="Users" color={KIND_COLORS.user}
          done={perKindDone.user} total={progress?.totals?.users || 0} />
        <KindRow label="Datasources" color={KIND_COLORS.datasource}
          done={perKindDone.datasource} total={progress?.totals?.datasources || 0} />
        <KindRow label="Dashboards" color={KIND_COLORS.dashboard}
          done={perKindDone.dashboard} total={progress?.totals?.dashboards || 0} />
        <KindRow label="Alert rules" color={KIND_COLORS.alert}
          done={perKindDone.alert} total={progress?.totals?.alerts || 0} />
        <KindRow label="Contact points" color={KIND_COLORS.contact_point}
          done={perKindDone.contact_point} total={progress?.totals?.contact_points || 0} />
        <KindRow label="Notification policy" color={KIND_COLORS.notification_policy}
          done={perKindDone.notification_policy} total={progress?.totals?.notification_policy || 0} />
      </div>

      {/* summary counters */}
      {summary && (
        <div className="grid grid-cols-4 gap-3 pt-2 border-t border-slate-100">
          {['created', 'updated', 'skipped', 'failed'].map((k) => (
            <div key={k} className="rounded-md border border-slate-200 p-3">
              <div className="text-xs uppercase text-slate-500">{k}</div>
              <div className="text-2xl font-semibold text-slate-800 tabular-nums">
                {summary[k] ?? 0}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const DETAIL_FILTERS = [
  { key: 'all',     label: 'All' },
  { key: 'created', label: 'Created' },
  { key: 'updated', label: 'Updated' },
  { key: 'skipped', label: 'Skipped' },
  { key: 'failed',  label: 'Failed' },
];

function DetailsTab({ results }) {
  const [filter, setFilter] = useState('all');

  const counts = useMemo(() => {
    const c = { all: 0, created: 0, updated: 0, skipped: 0, failed: 0 };
    (results || []).forEach((r) => {
      c.all += 1;
      if (c[r.status] !== undefined) c[r.status] += 1;
    });
    return c;
  }, [results]);

  const visible = useMemo(
    () => (filter === 'all' ? results : (results || []).filter((r) => r.status === filter)),
    [results, filter]
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {DETAIL_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`text-xs px-3 py-1.5 rounded-full border transition ${
              filter === f.key
                ? 'bg-slate-800 text-white border-slate-800'
                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
            }`}
          >
            {f.label}
            <span className="ml-1.5 opacity-70">{counts[f.key] || 0}</span>
          </button>
        ))}
      </div>

      <div className="max-h-96 overflow-y-auto border border-slate-100 rounded-md divide-y divide-slate-100">
        {(visible || []).length === 0 && (
          <div className="p-8 text-center text-sm text-slate-400">No items</div>
        )}
        {(visible || []).map((r, i) => (
          <div key={i} className="px-4 py-2 flex items-center gap-3 text-sm">
            <span className={`badge ${KIND_COLORS[r.kind] || 'bg-slate-100'}`}>
              {r.kind}
            </span>
            <span className="flex-1 truncate text-slate-700">{r.name}</span>
            {r.message && (
              <span
                className="truncate max-w-xs text-xs text-slate-500"
                title={r.message}
              >
                {r.message}
              </span>
            )}
            <span className={`badge ${STATUS_COLORS[r.status]}`}>{r.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MigrationProgress({ running, progress, results, summary }) {
  const [tab, setTab] = useState('progress');
  const hasActivity = running || progress || (results && results.length > 0);

  const TABS = [
    { key: 'progress', label: 'Percentage' },
    { key: 'details',  label: 'Status',    badge: results?.length || 0 },
  ];

  return (
    <div className="card">
      <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition ${
                tab === t.key
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              {t.label}
              {typeof t.badge === 'number' && t.badge > 0 && (
                <span className="ml-2 badge bg-slate-100 text-slate-600">
                  {t.badge}
                </span>
              )}
            </button>
          ))}
        </div>
        {running && (
          <span className="flex items-center gap-2 text-sm text-slate-600">
            <span className="h-2 w-2 rounded-full bg-brand-500 animate-pulse" />
            Running…
          </span>
        )}
      </div>
      <div className="p-5">
        {!hasActivity ? (
          <div className="py-12 text-center text-sm text-slate-400">
            Click <span className="font-medium text-slate-600">Start migration</span> to see live progress here.
          </div>
        ) : tab === 'progress' ? (
          <ProgressTab progress={progress} results={results} summary={summary} />
        ) : (
          <DetailsTab results={results} />
        )}
      </div>
    </div>
  );
}
