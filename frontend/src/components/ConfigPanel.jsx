import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { verify } from '../api/client';

function GrafanaForm({ title, value, onChange }) {
  const [showToken, setShowToken] = useState(false);
  const [checking, setChecking] = useState(false);

  const check = async () => {
    if (!value.url || !value.token) {
      toast.error('URL and token required');
      return;
    }
    setChecking(true);
    try {
      await verify(value);
      toast.success(`${title}: connected`);
    } catch (e) {
      toast.error(`${title}: ${e.response?.data?.detail || e.message}`);
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
        <button className="btn-secondary" onClick={check} disabled={checking}>
          {checking ? 'Checking…' : 'Test connection'}
        </button>
      </div>
      <div>
        <label className="label">Grafana URL</label>
        <input
          className="input"
          placeholder="http://grafana.example.com:3000"
          value={value.url}
          onChange={(e) => onChange({ ...value, url: e.target.value })}
        />
      </div>
      <div>
        <label className="label">API Token</label>
        <div className="flex gap-2">
          <input
            className="input"
            type={showToken ? 'text' : 'password'}
            placeholder="glsa_…"
            value={value.token}
            onChange={(e) => onChange({ ...value, token: e.target.value })}
          />
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setShowToken((s) => !s)}
          >
            {showToken ? 'Hide' : 'Show'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ConfigPanel({ source, target, setSource, setTarget }) {
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <GrafanaForm title="Source" value={source} onChange={setSource} />
      <GrafanaForm title="Target" value={target} onChange={setTarget} />
    </div>
  );
}
