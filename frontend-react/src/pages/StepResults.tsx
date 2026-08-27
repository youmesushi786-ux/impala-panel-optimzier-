import { useState, useMemo } from 'react';
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize2, X, Download, FileText, CheckCircle2, ArrowLeft, Layers3, DollarSign, QrCode, Package } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { api } from '../api/client';

interface Props {
  results: any;
  requestData: any;
  onBack: () => void;
}

const TABS = [
  { id: 'layout', label: 'Layouts', icon: Layers3 },
  { id: 'boq', label: 'BOQ', icon: FileText },
  { id: 'pricing', label: 'Pricing', icon: DollarSign },
  { id: 'stickers', label: 'Stickers', icon: QrCode },
  { id: 'stock', label: 'Stock Impact', icon: Package },
];

export function StepResults({ results, requestData, onBack }: Props) {
  const [tab, setTab] = useState('layout');
  const [layoutIdx, setLayoutIdx] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [showCuts, setShowCuts] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [exportReport, setExportReport] = useState(false);
  const [exportLabels, setExportLabels] = useState(false);

  if (!results) return null;

  const layouts = results.layouts || [];
  const activeLayout = layouts[layoutIdx];

  const download = (blob: Blob, name: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name; a.click();
    URL.revokeObjectURL(url);
  };

  const handleReport = async () => {
    setExportReport(true);
    try { download(await api.exportReportPdf(requestData), 'report.pdf'); }
    finally { setExportReport(false); }
  };

  const handleLabels = async () => {
    setExportLabels(true);
    try { download(await api.exportLabelsPdf(requestData), 'labels.pdf'); }
    finally { setExportLabels(false); }
  };

  const handleConfirm = async () => {
    setConfirming(true);
    try { await api.confirmJob(results.report_id); }
    finally { setConfirming(false); }
  };

  const renderLayout = (isFullscreen = false) => {
    if (!activeLayout) return null;
    const bw = activeLayout.board_width, bh = activeLayout.board_length;
    const maxW = isFullscreen ? 1500 : 900, maxH = isFullscreen ? 900 : 550;
    const scale = Math.min(maxW / bw, maxH / bh) * zoom;

    return (
      <div className="overflow-auto p-6 bg-slate-950 rounded-xl border border-slate-800">
        <div className="relative mx-auto bg-slate-900 border-2 border-amber-500/40 shadow-[0_0_40px_rgba(245,158,11,0.15)]" style={{ width: bw * scale, height: bh * scale }}>
          {activeLayout.panels?.map((p: any, i: number) => (
            <div key={i} className={`absolute overflow-hidden border rounded-sm transition-all hover:z-10 hover:shadow-[0_0_15px_rgba(6,182,212,0.5)] ${p.rotated ? 'bg-cyan-500/25 border-cyan-400 text-cyan-100' : 'bg-amber-500/25 border-amber-400 text-amber-100'}`}
              style={{ left: p.x * scale, top: p.y * scale, width: Math.max(p.width * scale, 20), height: Math.max(p.length * scale, 20), padding: 3 }}
              title={`${p.label || 'Panel'} ${p.width}×${p.length}`}>
              <div className="text-[10px] font-bold font-mono truncate">{p.label || `P${i + 1}`}</div>
              <div className="text-[9px] font-mono opacity-80">{Math.round(p.width)}×{Math.round(p.length)}</div>
              {p.rotated && <div className="text-[8px] font-mono">↻ ROT</div>}
            </div>
          ))}
          {showCuts && activeLayout.cuts?.map((c: any, i: number) => {
            const isV = c.orientation === 'V';
            return (
              <div key={i} className="absolute pointer-events-none" style={{
                left: Math.min(c.x1, c.x2) * scale, top: Math.min(c.y1, c.y2) * scale,
                width: isV ? 2 : Math.abs(c.x2 - c.x1) * scale,
                height: isV ? Math.abs(c.y2 - c.y1) * scale : 2,
                backgroundColor: '#EF4444', boxShadow: '0 0 8px rgba(239,68,68,0.6)',
              }} />
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-[1800px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="w-4 h-4" />} onClick={onBack} className="mb-3">Back</Button>
          <h1 className="text-3xl sm:text-4xl font-display font-bold">Optimization Report</h1>
          <div className="flex flex-wrap items-center gap-2 mt-2 text-sm text-slate-400">
            <Badge variant="cyan" size="sm">{results.report_id}</Badge>
            <span>•</span>
            <span>{results.request_summary?.project_name}</span>
            <span>•</span>
            <span>{results.request_summary?.customer_name}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" leftIcon={<Download className="w-4 h-4" />} isLoading={exportReport} onClick={handleReport}>Report PDF</Button>
          <Button variant="outline" size="sm" leftIcon={<QrCode className="w-4 h-4" />} isLoading={exportLabels} onClick={handleLabels}>Labels PDF</Button>
          <Button size="sm" leftIcon={<CheckCircle2 className="w-4 h-4" />} isLoading={confirming} onClick={handleConfirm}>Confirm & Deduct</Button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Boards Used', value: results.optimization.total_boards, color: 'amber', unit: 'sheets' },
          { label: 'Panels Cut', value: results.optimization.total_panels, color: 'cyan', unit: 'pieces' },
          { label: 'Waste', value: `${results.optimization.total_waste_percent.toFixed(1)}%`, color: 'rose', unit: 'material' },
          { label: 'Edge Banding', value: `${results.optimization.total_edging_meters.toFixed(1)}m`, color: 'emerald', unit: 'total' },
        ].map((k) => (
          <Card key={k.label} variant="glass" glow={k.color as any} className="!p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">{k.label}</p>
              <Badge variant={k.color as any} size="sm">{k.unit}</Badge>
            </div>
            <p className={`text-3xl font-mono font-bold text-${k.color}-400`}>{k.value}</p>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-800 overflow-x-auto">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button key={t.id} onClick={() => setTab(t.id)} className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold whitespace-nowrap transition-all border-b-2 ${
              tab === t.id ? 'text-amber-400 border-amber-400' : 'text-slate-400 border-transparent hover:text-white'
            }`}>
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* LAYOUT TAB */}
      {tab === 'layout' && activeLayout && (
        <Card variant="glass">
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <Button variant="outline" size="sm" leftIcon={<ChevronLeft className="w-4 h-4" />} onClick={() => setLayoutIdx(Math.max(0, layoutIdx - 1))} disabled={layoutIdx === 0}>Prev</Button>
            <Badge variant="amber" size="lg">Board {layoutIdx + 1} of {layouts.length}</Badge>
            <Button variant="outline" size="sm" rightIcon={<ChevronRight className="w-4 h-4" />} onClick={() => setLayoutIdx(Math.min(layouts.length - 1, layoutIdx + 1))} disabled={layoutIdx === layouts.length - 1}>Next</Button>
            <div className="flex-1" />
            <Button variant="ghost" size="sm" onClick={() => setZoom(Math.max(0.4, zoom - 0.2))}><ZoomOut className="w-4 h-4" /></Button>
            <span className="text-xs font-mono text-slate-400 px-2">{Math.round(zoom * 100)}%</span>
            <Button variant="ghost" size="sm" onClick={() => setZoom(Math.min(3, zoom + 0.2))}><ZoomIn className="w-4 h-4" /></Button>
            <Button variant="outline" size="sm" onClick={() => setShowCuts(!showCuts)}>{showCuts ? 'Hide' : 'Show'} Cuts</Button>
            <Button variant="outline" size="sm" leftIcon={<Maximize2 className="w-4 h-4" />} onClick={() => setFullscreen(true)}>Fullscreen</Button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4 text-xs font-mono">
            <div className="p-2 rounded bg-slate-900/60"><span className="text-slate-500">Size:</span> {activeLayout.board_width}×{activeLayout.board_length}</div>
            <div className="p-2 rounded bg-slate-900/60"><span className="text-slate-500">Efficiency:</span> <span className="text-emerald-400">{activeLayout.efficiency_percent.toFixed(1)}%</span></div>
            <div className="p-2 rounded bg-slate-900/60"><span className="text-slate-500">Panels:</span> {activeLayout.panel_count}</div>
            <div className="p-2 rounded bg-slate-900/60"><span className="text-slate-500">Waste:</span> {Math.round(activeLayout.waste_area_mm2)}mm²</div>
          </div>

          {renderLayout()}
        </Card>
      )}

      {/* BOQ TAB */}
      {tab === 'boq' && results.boq?.items?.length > 0 && (
        <Card variant="glass" title="Bill of Quantities">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-800">
                <tr className="text-left text-xs uppercase text-slate-500">
                  {['#', 'Description', 'Size', 'Qty', 'Unit', 'Edges', 'Material'].map((h) => <th key={h} className="p-3 font-semibold">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {results.boq.items.map((item: any) => (
                  <tr key={item.item_no} className="border-b border-slate-800/60 hover:bg-slate-800/30">
                    <td className="p-3 font-mono text-amber-400">{item.item_no}</td>
                    <td className="p-3 font-semibold">{item.description}</td>
                    <td className="p-3 font-mono text-slate-400">{item.size}</td>
                    <td className="p-3 font-mono">{item.quantity}</td>
                    <td className="p-3 text-slate-400">{item.unit}</td>
                    <td className="p-3"><Badge variant="emerald" size="sm">{item.edges}</Badge></td>
                    <td className="p-3 text-xs text-slate-400">{item.board_type} {item.thickness_mm}mm {item.colour}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* PRICING TAB */}
      {tab === 'pricing' && results.boq?.pricing && (
        <Card variant="glass" title="Pricing Summary">
          <div className="overflow-x-auto mb-6">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-800">
                <tr className="text-left text-xs uppercase text-slate-500">
                  {['Item', 'Description', 'Qty', 'Unit', 'Unit Price', 'Amount'].map((h) => <th key={h} className="p-3">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {results.boq.pricing.lines?.map((l: any, i: number) => (
                  <tr key={i} className="border-b border-slate-800/60">
                    <td className="p-3 font-mono">{l.item}</td>
                    <td className="p-3">{l.description}</td>
                    <td className="p-3 font-mono">{l.quantity}</td>
                    <td className="p-3 text-slate-400">{l.unit}</td>
                    <td className="p-3 font-mono text-amber-400">{l.unit_price}</td>
                    <td className="p-3 font-mono font-bold">{l.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Card variant="terminal" className="!p-4"><p className="text-[10px] uppercase text-slate-500">Subtotal</p><p className="text-2xl font-mono font-bold">{results.boq.pricing.subtotal}</p></Card>
            <Card variant="terminal" className="!p-4"><p className="text-[10px] uppercase text-slate-500">{results.boq.pricing.tax_name}</p><p className="text-2xl font-mono font-bold text-cyan-400">{results.boq.pricing.tax_amount}</p></Card>
            <Card variant="terminal" className="!p-4"><p className="text-[10px] uppercase text-slate-500">Total</p><p className="text-2xl font-mono font-bold text-amber-400">{results.boq.pricing.total}</p></Card>
            <Card variant="terminal" className="!p-4"><p className="text-[10px] uppercase text-slate-500">Currency</p><p className="text-2xl font-mono font-bold">{results.boq.pricing.currency}</p></Card>
          </div>
        </Card>
      )}

      {/* STICKERS TAB */}
      {tab === 'stickers' && (
        <Card variant="glass" title="Sticker Tracking">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {results.stickers?.map((s: any, i: number) => (
              <div key={i} className="p-4 rounded-xl bg-slate-800/40 border border-slate-700 hover:border-amber-500/40 transition">
                <div className="flex items-center justify-between mb-2">
                  <Badge variant="cyan" size="sm">Board {s.board_number}</Badge>
                  <QrCode className="w-5 h-5 text-slate-500" />
                </div>
                <p className="text-xs font-mono text-slate-500 mb-1">{s.serial_number}</p>
                <p className="text-sm font-semibold">{s.panel_label}</p>
                {s.qr_url && (
                  <a href={s.qr_url} target="_blank" rel="noreferrer" className="text-xs text-amber-400 hover:underline mt-2 inline-block">Open tracking →</a>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* STOCK IMPACT TAB */}
      {tab === 'stock' && results.stock_impact?.length > 0 && (
        <Card variant="glass" title="Stock Impact Analysis">
          <div className="space-y-2">
            {results.stock_impact.map((s: any, i: number) => {
              const critical = s.projected_balance < 0;
              return (
                <div key={i} className={`p-4 rounded-xl border ${critical ? 'bg-rose-500/10 border-rose-500/40' : 'bg-slate-800/40 border-slate-700'}`}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-semibold">{s.board_label}</p>
                      <p className="text-xs text-slate-400 font-mono mt-1">${s.price_per_board}/board</p>
                    </div>
                    <div className="flex items-center gap-4 font-mono text-sm">
                      <div><p className="text-[10px] text-slate-500 uppercase">Current</p><p className="font-bold">{s.current_quantity}</p></div>
                      <div><p className="text-[10px] text-slate-500 uppercase">Need</p><p className="font-bold text-amber-400">-{s.required_quantity}</p></div>
                      <div><p className="text-[10px] text-slate-500 uppercase">After</p><p className={`font-bold ${critical ? 'text-rose-400' : 'text-emerald-400'}`}>{s.projected_balance}</p></div>
                      <Badge variant={critical ? 'rose' : 'emerald'} pulse={critical}>{s.stock_status}</Badge>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* FULLSCREEN */}
      {fullscreen && (
        <div className="fixed inset-0 z-50 bg-black/95 backdrop-blur-lg p-4 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-display font-bold">Board #{activeLayout.board_number}</h2>
            <Button variant="ghost" onClick={() => setFullscreen(false)} leftIcon={<X className="w-5 h-5" />}>Close</Button>
          </div>
          <div className="flex-1 overflow-auto">{renderLayout(true)}</div>
        </div>
      )}
    </div>
  );
}
