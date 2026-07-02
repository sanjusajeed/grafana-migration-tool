import React, { useCallback, useState } from 'react';
import toast from 'react-hot-toast';
import ConfigPanel from './components/ConfigPanel';
import ItemList from './components/ItemList';
import MigrationProgress from './components/MigrationProgress';
import {
  fetchAlerts,
  fetchContactPoints,
  fetchDashboards,
  fetchDatasources,
  fetchUsers,
  migrateStream,
} from './api/client';

const EMPTY_CFG = { url: '', token: '' };

function useSelection() {
  const [selected, setSelected] = useState(new Set());
  const toggle = (k) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(k) ? next.delete(k) : next.add(k);
      return next;
    });
  const selectAll = (keys) =>
    setSelected((prev) => new Set([...prev, ...keys]));
  const clear = (keys) =>
    setSelected((prev) => {
      const next = new Set(prev);
      keys.forEach((k) => next.delete(k));
      return next;
    });
  const reset = () => setSelected(new Set());
  return { selected, toggle, selectAll, clear, reset };
}

const ROLE_COLORS = {
  Admin: 'bg-red-100 text-red-700',
  Editor: 'bg-blue-100 text-blue-700',
  Viewer: 'bg-slate-100 text-slate-600',
};

export default function App() {
  const [source, setSource] = useState(EMPTY_CFG);
  const [target, setTarget] = useState(EMPTY_CFG);
  const [onConflict, setOnConflict] = useState('update');

  const [users, setUsers] = useState([]);
  const [dashboards, setDashboards] = useState([]);
  const [datasources, setDatasources] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [contactPoints, setContactPoints] = useState([]);
  const [migrateNotifPolicy, setMigrateNotifPolicy] = useState(false);

  const [loading, setLoading] = useState({ users: false, dash: false, ds: false, al: false, cp: false });
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(null);
  const [liveResults, setLiveResults] = useState([]);
  const [summary, setSummary] = useState(null);

  const userSel = useSelection();
  const dashSel = useSelection();
  const dsSel = useSelection();
  const alSel = useSelection();
  const cpSel = useSelection();

  const requireSource = useCallback(() => {
    if (!source.url || !source.token) {
      toast.error('Enter Source URL and token first');
      return false;
    }
    return true;
  }, [source]);

  const loadUsers = async () => {
    if (!requireSource()) return;
    setLoading((l) => ({ ...l, users: true }));
    try {
      setUsers(await fetchUsers(source));
      toast.success('Users loaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally {
      setLoading((l) => ({ ...l, users: false }));
    }
  };
  const loadDashboards = async () => {
    if (!requireSource()) return;
    setLoading((l) => ({ ...l, dash: true }));
    try {
      setDashboards(await fetchDashboards(source));
      toast.success('Dashboards loaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally {
      setLoading((l) => ({ ...l, dash: false }));
    }
  };
  const loadDatasources = async () => {
    if (!requireSource()) return;
    setLoading((l) => ({ ...l, ds: true }));
    try {
      setDatasources(await fetchDatasources(source));
      toast.success('Datasources loaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally {
      setLoading((l) => ({ ...l, ds: false }));
    }
  };
  const loadAlerts = async () => {
    if (!requireSource()) return;
    setLoading((l) => ({ ...l, al: true }));
    try {
      setAlerts(await fetchAlerts(source));
      toast.success('Alerts loaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally {
      setLoading((l) => ({ ...l, al: false }));
    }
  };
  const loadContactPoints = async () => {
    if (!requireSource()) return;
    setLoading((l) => ({ ...l, cp: true }));
    try {
      setContactPoints(await fetchContactPoints(source));
      toast.success('Contact points loaded');
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message);
    } finally {
      setLoading((l) => ({ ...l, cp: false }));
    }
  };

  const loadAll = async () => {
    if (!requireSource()) return;
    await Promise.all([
      loadUsers(),
      loadDashboards(),
      loadDatasources(),
      loadAlerts(),
      loadContactPoints(),
    ]);
  };

  const run = async () => {
    if (!source.url || !target.url || !source.token || !target.token) {
      toast.error('Configure both source and target');
      return;
    }
    const selection = {
      users: [...userSel.selected],
      all_users: false,
      dashboards: [...dashSel.selected],
      all_dashboards: false,
      datasources: [...dsSel.selected],
      all_datasources: false,
      alerts: [...alSel.selected],
      all_alerts: false,
      contact_points: [...cpSel.selected],
      all_contact_points: false,
      notification_policy: migrateNotifPolicy,
    };
    const nothingSelected =
      !selection.users.length &&
      !selection.dashboards.length &&
      !selection.datasources.length &&
      !selection.alerts.length &&
      !selection.contact_points.length &&
      !selection.notification_policy;
    if (nothingSelected) {
      toast.error('Select at least one item to migrate');
      return;
    }
    setRunning(true);
    setProgress(null);
    setLiveResults([]);
    setSummary(null);

    let finalSummary = null;
    try {
      await migrateStream(
        { source, target, selection, on_conflict: onConflict },
        (evt) => {
          if (evt.type === 'plan') {
            setProgress({ done: 0, totals: evt.totals });
          } else if (evt.type === 'item') {
            setProgress((p) => ({
              ...(p || { totals: {} }),
              done: evt.progress.done,
              totals: { ...(p?.totals || {}), total: evt.progress.total },
            }));
            setLiveResults((prev) => [...prev, evt.result]);
          } else if (evt.type === 'done') {
            finalSummary = evt.summary;
            setSummary(evt.summary);
          } else if (evt.type === 'error') {
            toast.error(evt.message);
          }
        }
      );
      if (finalSummary) {
        if ((finalSummary.failed || 0) === 0) toast.success('Migration completed');
        else toast.error(`Completed with ${finalSummary.failed} failures`);
      }
    } catch (e) {
      toast.error(e.message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-800">Grafana Migration</h1>
            <p className="text-sm text-slate-500">
              Copy dashboards, datasources, users, and alert config between Grafana instances.
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        <ConfigPanel
          source={source}
          target={target}
          setSource={setSource}
          setTarget={setTarget}
        />

        <div className="card p-4 flex items-center gap-3 flex-wrap">
          <button className="btn-primary" onClick={loadAll}>
            Fetch from source
          </button>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-600">On conflict:</span>
            <select
              className="input max-w-[10rem]"
              value={onConflict}
              onChange={(e) => setOnConflict(e.target.value)}
            >
              <option value="update">Update existing</option>
              <option value="skip">Skip existing</option>
            </select>
          </div>
          <div className="flex-1" />
          <button className="btn-primary" onClick={run} disabled={running}>
            {running ? 'Migrating…' : 'Start migration'}
          </button>
        </div>

        <MigrationProgress
          running={running}
          progress={progress}
          results={liveResults}
          summary={summary}
        />

        {/* Users */}
        <ItemList
          title="Users"
          items={users}
          selected={userSel.selected}
          onToggle={userSel.toggle}
          onSelectAll={userSel.selectAll}
          onClear={userSel.clear}
          getKey={(u) => u.login}
          onRefresh={loadUsers}
          loading={loading.users}
          emptyHint="Click Fetch from source to load users (built-in admin excluded)"
          renderRow={(u) => (
            <div className="flex-1 min-w-0 flex items-center gap-3">
              <span className="font-medium text-slate-800 truncate">{u.name}</span>
              <span className="text-xs text-slate-400 truncate">{u.login}</span>
              <span className={`badge ${ROLE_COLORS[u.role] || 'bg-slate-100 text-slate-600'}`}>
                {u.role}
              </span>
            </div>
          )}
        />

        {/* Datasources */}
        <ItemList
          title="Datasources"
          items={datasources}
          selected={dsSel.selected}
          onToggle={dsSel.toggle}
          onSelectAll={dsSel.selectAll}
          onClear={dsSel.clear}
          getKey={(d) => d.uid || d.name}
          onRefresh={loadDatasources}
          loading={loading.ds}
          emptyHint="Click Fetch from source to load datasources"
          renderRow={(d) => (
            <div className="flex-1 min-w-0 flex items-center gap-3">
              <span className="font-medium text-slate-800 truncate">{d.name}</span>
              <span className="badge bg-purple-100 text-purple-700">{d.type}</span>
              {d.isDefault && (
                <span className="badge bg-amber-100 text-amber-700">default</span>
              )}
              <span className="text-xs text-slate-400 truncate">{d.url}</span>
            </div>
          )}
        />

        {/* Dashboards */}
        <ItemList
          title="Dashboards"
          items={dashboards}
          selected={dashSel.selected}
          onToggle={dashSel.toggle}
          onSelectAll={dashSel.selectAll}
          onClear={dashSel.clear}
          getKey={(d) => d.uid}
          onRefresh={loadDashboards}
          loading={loading.dash}
          emptyHint="Click Fetch from source to load dashboards"
          renderRow={(d) => (
            <div className="flex-1 min-w-0 flex items-center gap-3">
              <span className="font-medium text-slate-800 truncate">{d.title}</span>
              <span className="badge bg-indigo-100 text-indigo-700">
                {d.folder || 'General'}
              </span>
              <span className="text-xs text-slate-400 truncate">{d.uid}</span>
            </div>
          )}
        />

        {/* Alert rule groups */}
        <ItemList
          title="Alert rule groups"
          items={alerts}
          selected={alSel.selected}
          onToggle={alSel.toggle}
          onSelectAll={alSel.selectAll}
          onClear={alSel.clear}
          getKey={(a) => a.key}
          onRefresh={loadAlerts}
          loading={loading.al}
          emptyHint="Click Fetch from source to load alert rules"
          renderRow={(a) => (
            <div className="flex-1 min-w-0 flex items-center gap-3">
              <span className="font-medium text-slate-800 truncate">{a.group}</span>
              <span className="badge bg-pink-100 text-pink-700">{a.namespace}</span>
              <span className="text-xs text-slate-500">
                {a.ruleCount} rules · {a.interval}
              </span>
            </div>
          )}
        />

        {/* Contact points */}
        <ItemList
          title="Contact points"
          items={contactPoints}
          selected={cpSel.selected}
          onToggle={cpSel.toggle}
          onSelectAll={cpSel.selectAll}
          onClear={cpSel.clear}
          getKey={(cp) => cp.uid}
          onRefresh={loadContactPoints}
          loading={loading.cp}
          emptyHint="Click Fetch from source to load contact points"
          renderRow={(cp) => (
            <div className="flex-1 min-w-0 flex items-center gap-3">
              <span className="font-medium text-slate-800 truncate">{cp.name}</span>
              <span className="badge bg-orange-100 text-orange-700">{cp.type}</span>
              <span className="text-xs text-slate-400 truncate">{cp.uid}</span>
            </div>
          )}
        />

        {/* Notification policy */}
        <div className="card p-5">
          <div className="flex items-start gap-3">
            <input
              id="notif-policy"
              type="checkbox"
              className="mt-0.5 h-4 w-4 cursor-pointer"
              checked={migrateNotifPolicy}
              onChange={(e) => setMigrateNotifPolicy(e.target.checked)}
            />
            <label htmlFor="notif-policy" className="cursor-pointer select-none">
              <div className="font-semibold text-slate-800">Notification policy</div>
              <div className="text-sm text-slate-500 mt-0.5">
                Copies the full routing tree from source to target, replacing any existing policy.
                <span className="block mt-1 text-xs text-slate-400">
                  All contact points and mute timings are automatically included — no need to select them separately.
                </span>
              </div>
            </label>
          </div>
        </div>

      </main>
    </div>
  );
}
