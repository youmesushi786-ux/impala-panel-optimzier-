import { useState } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { api } from '../api/client';

interface Props {
  results: any;
  requestData: any;
  onBack: () => void;
  projectName?: string;
  customerName?: string;
}

export function StepResults({ results, requestData, onBack }: Props) {
  const [confirming, setConfirming] = useState(false);
  const [exportingReport, setExportingReport] = useState(false);
  const [exportingLabels, setExportingLabels] = useState(false);
  const [confirmMessage, setConfirmMessage] = useState('');
  const [error, setError] = useState('');

  const [showCuts, setShowCuts] = useState(true);
  const [activeLayoutIndex, setActiveLayoutIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);

  if (!results) return null;

  const layouts = results.layouts || [];
  const activeLayout = layouts[activeLayoutIndex] || null;
  const stickers = results.stickers || [];

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const handleExportReport = async () => {
    try {
      setExportingReport(true);
      setError('');
      const blob = await api.exportReportPdf(requestData);
      downloadBlob(blob, 'optimization_report.pdf');
    } catch (e: any) {
      setError(e.message || 'Failed to export report');
    } finally {
      setExportingReport(false);
    }
  };

  const handleExportLabels = async () => {
    try {
      setExportingLabels(true);
      setError('');
      const blob = await api.exportLabelsPdf(requestData);
      downloadBlob(blob, 'panel_labels.pdf');
    } catch (e: any) {
      setError(e.message || 'Failed to export labels');
    } finally {
      setExportingLabels(false);
    }
  };

  const handleConfirmJob = async () => {
    try {
      setConfirming(true);
      setError('');
      const response = await api.confirmJob(results.report_id);
      setConfirmMessage(response.message);
    } catch (e: any) {
      setError(e.message || 'Failed to confirm job');
    } finally {
      setConfirming(false);
    }
  };

  const goPrevLayout = () => {
    setActiveLayoutIndex((prev) => Math.max(prev - 1, 0));
  };

  const goNextLayout = () => {
    setActiveLayoutIndex((prev) => Math.min(prev + 1, layouts.length - 1));
  };

  const zoomIn = () => setZoom((z) => Math.min(z + 0.2, 3));
  const zoomOut = () => setZoom((z) => Math.max(z - 0.2, 0.4));
  const resetZoom = () => setZoom(1);

  const renderLayout = (layout: any, isFullscreen = false) => {
    const boardWidth = Number(layout.board_width || 0);
    const boardHeight = Number(layout.board_length || 0);

    if (!boardWidth || !boardHeight) {
      return (
        <div className="p-4 border rounded-lg text-sm text-gray-500">
          Invalid board size
        </div>
      );
    }

    const maxWidth = isFullscreen ? 1400 : 950;
    const maxHeight = isFullscreen ? 850 : 520;
    const baseScale = Math.min(maxWidth / boardWidth, maxHeight / boardHeight);
    const scale = baseScale * zoom;

    const renderWidth = boardWidth * scale;
    const renderHeight = boardHeight * scale;

    return (
      <div className="overflow-auto border rounded-2xl bg-slate-50 p-4 shadow-inner">
        <div className="mb-4 flex flex-wrap gap-4 text-sm text-gray-700">
          <div className="font-semibold">Board #{layout.board_number}</div>
          <div>{boardWidth} × {boardHeight} mm</div>
          <div>Efficiency: {layout.efficiency_percent.toFixed(2)}%</div>
          <div>Waste: {Math.round(layout.waste_area_mm2)} mm²</div>
          <div>Panels: {layout.panel_count}</div>
          <div>Zoom: {(zoom * 100).toFixed(0)}%</div>
        </div>

        <div
          className="relative bg-white border-[3px] border-gray-900 shadow-md"
          style={{
            width: `${renderWidth}px`,
            height: `${renderHeight}px`,
          }}
        >
          <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-xs font-semibold text-gray-700 bg-white px-2 py-1 rounded border">
            {boardWidth} mm
          </div>
          <div className="absolute -left-12 top-1/2 -translate-y-1/2 -rotate-90 text-xs font-semibold text-gray-700 bg-white px-2 py-1 rounded border">
            {boardHeight} mm
          </div>

          {layout.panels?.map((panel: any, idx: number) => {
            const x = Number(panel.x || 0) * scale;
            const y = Number(panel.y || 0) * scale;
            const w = Number(panel.width || 0) * scale;
            const h = Number(panel.length || 0) * scale;

            const smallBox = w < 80 || h < 50;

            return (
              <div
                key={idx}
                className={`absolute border rounded-sm shadow-sm overflow-hidden ${
                  panel.rotated
                    ? 'bg-blue-100 border-blue-600 text-blue-900'
                    : 'bg-orange-100 border-orange-600 text-orange-900'
                }`}
                style={{
                  left: `${x}px`,
                  top: `${y}px`,
                  width: `${Math.max(w, 18)}px`,
                  height: `${Math.max(h, 18)}px`,
                  padding: '4px',
                  boxSizing: 'border-box',
                }}
                title={`${panel.label || `Panel ${panel.panel_index + 1}`} - ${panel.width} x ${panel.length}`}
              >
                <div className={`font-bold truncate ${smallBox ? 'text-[9px]' : 'text-[12px]'}`}>
                  {panel.label || `P${panel.panel_index + 1}`}
                </div>
                <div className={`${smallBox ? 'text-[8px]' : 'text-[10px]'} truncate`}>
                  {Math.round(panel.width)} × {Math.round(panel.length)}
                </div>
                <div className={`${smallBox ? 'text-[8px]' : 'text-[10px]'} font-medium`}>
                  {panel.rotated ? 'Rotated' : 'Original'}
                </div>
              </div>
            );
          })}

          {showCuts &&
            layout.cuts?.map((cut: any, idx: number) => {
              const x1 = Number(cut.x1 || 0) * scale;
              const y1 = Number(cut.y1 || 0) * scale;
              const x2 = Number(cut.x2 || 0) * scale;
              const y2 = Number(cut.y2 || 0) * scale;
              const isVertical = cut.orientation === 'V';

              return (
                <div key={`cut-${idx}`}>
                  <div
                    className="absolute pointer-events-none"
                    style={{
                      left: `${Math.min(x1, x2)}px`,
                      top: `${Math.min(y1, y2)}px`,
                      width: isVertical ? '2px' : `${Math.abs(x2 - x1)}px`,
                      height: isVertical ? `${Math.abs(y2 - y1)}px` : '2px',
                      backgroundColor: '#111827',
                      opacity: 0.9,
                    }}
                  />
                  <div
                    className="absolute bg-gray-900 text-white text-[9px] px-1 py-[1px] rounded pointer-events-none"
                    style={{
                      left: `${Math.min(x1, x2) + 4}px`,
                      top: `${Math.min(y1, y2) + 4}px`,
                    }}
                  >
                    {cut.sequence || cut.id}
                  </div>
                </div>
              );
            })}
        </div>
      </div>
    );
  };

  return (
    <div className="p-6 max-w-[1900px] mx-auto space-y-6">
      <div className="flex justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-4xl font-bold text-gray-900">Optimization Results</h1>
          <p className="text-gray-600 mt-2">
            Project: <strong>{results.request_summary?.project_name}</strong> • Customer:{' '}
            <strong>{results.request_summary?.customer_name}</strong>
          </p>
          <p className="text-gray-500 mt-1 text-sm">Report ID: {results.report_id}</p>
        </div>

        <div className="flex gap-3 flex-wrap">
          <Button variant="outline" onClick={onBack}>Back</Button>
          <Button variant="outline" onClick={handleExportReport}>
            {exportingReport ? 'Exporting Report...' : 'Print / Save PDF'}
          </Button>
          <Button variant="outline" onClick={handleExportLabels}>
            {exportingLabels ? 'Exporting Labels...' : 'Export Labels PDF'}
          </Button>
          <Button onClick={handleConfirmJob}>
            {confirming ? 'Confirming...' : 'Confirm Job & Deduct Stock'}
          </Button>
        </div>
      </div>

      {results.stock_impact?.length === 0 && (
        <div className="p-3 rounded border border-red-200 bg-red-50 text-red-700">
          No stock impact found for this job.
        </div>
      )}

      {confirmMessage && (
        <div className="p-3 rounded border border-green-200 bg-green-50 text-green-700">
          {confirmMessage}
        </div>
      )}

      {error && (
        <div className="p-3 rounded border border-red-200 bg-red-50 text-red-700">
          {error}
        </div>
      )}

      <Card title="Optimization Summary" hover>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded bg-blue-50">
            <div className="text-sm text-blue-700">Boards Used</div>
            <div className="text-2xl font-bold">{results.optimization.total_boards}</div>
          </div>
          <div className="p-4 rounded bg-green-50">
            <div className="text-sm text-green-700">Total Panels</div>
            <div className="text-2xl font-bold">{results.optimization.total_panels}</div>
          </div>
          <div className="p-4 rounded bg-amber-50">
            <div className="text-sm text-amber-700">Waste %</div>
            <div className="text-2xl font-bold">{results.optimization.total_waste_percent.toFixed(2)}%</div>
          </div>
          <div className="p-4 rounded bg-purple-50">
            <div className="text-sm text-purple-700">Edging</div>
            <div className="text-2xl font-bold">{results.optimization.total_edging_meters.toFixed(2)} m</div>
          </div>
        </div>
      </Card>

      <Card title="Sticker Tracking / QR Links" hover>
        {stickers.length === 0 ? (
          <p className="text-gray-500">No stickers generated.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-3 py-2 text-left">Serial</th>
                  <th className="px-3 py-2 text-left">Panel</th>
                  <th className="px-3 py-2 text-left">Board</th>
                  <th className="px-3 py-2 text-left">QR Link</th>
                </tr>
              </thead>
              <tbody>
                {stickers.map((sticker: any, idx: number) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="px-3 py-2">{sticker.serial_number}</td>
                    <td className="px-3 py-2">{sticker.panel_label}</td>
                    <td className="px-3 py-2">{sticker.board_number}</td>
                    <td className="px-3 py-2">
                      {sticker.qr_url ? (
                        <a
                          href={sticker.qr_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 underline break-all"
                        >
                          Open Tracking
                        </a>
                      ) : (
                        <span className="text-gray-500">No QR URL</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {results.stock_impact?.length > 0 && (
        <Card title="Stock Impact" hover>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-3 py-2 text-left">Board</th>
                  <th className="px-3 py-2 text-left">Current</th>
                  <th className="px-3 py-2 text-left">Required</th>
                  <th className="px-3 py-2 text-left">Projected</th>
                  <th className="px-3 py-2 text-left">Price</th>
                  <th className="px-3 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {results.stock_impact.map((row: any, idx: number) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="px-3 py-2">{row.board_label}</td>
                    <td className="px-3 py-2">{row.current_quantity}</td>
                    <td className="px-3 py-2">{row.required_quantity}</td>
                    <td className="px-3 py-2">{row.projected_balance}</td>
                    <td className="px-3 py-2">{row.price_per_board}</td>
                    <td className="px-3 py-2">{row.stock_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card title="2D Cutting Layout Viewer" hover>
        {layouts.length > 0 && (
          <>
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <Button variant="outline" size="sm" onClick={goPrevLayout} disabled={activeLayoutIndex === 0}>
                Previous
              </Button>

              <div className="px-3 py-2 rounded-lg bg-gray-100 text-sm font-medium">
                Board {activeLayoutIndex + 1} of {layouts.length}
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={goNextLayout}
                disabled={activeLayoutIndex === layouts.length - 1}
              >
                Next
              </Button>

              <Button variant="outline" size="sm" onClick={() => setShowCuts(!showCuts)}>
                {showCuts ? 'Hide Cuts' : 'Show Cuts'}
              </Button>

              <Button variant="outline" size="sm" onClick={zoomOut}>
                Zoom -
              </Button>

              <Button variant="outline" size="sm" onClick={resetZoom}>
                Reset Zoom
              </Button>

              <Button variant="outline" size="sm" onClick={zoomIn}>
                Zoom +
              </Button>

              <Button variant="outline" size="sm" onClick={() => setFullscreen(true)}>
                Fullscreen
              </Button>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              {layouts.map((layout: any, idx: number) => (
                <button
                  key={layout.board_number}
                  type="button"
                  onClick={() => setActiveLayoutIndex(idx)}
                  className={`px-3 py-1 rounded-lg text-sm border ${
                    idx === activeLayoutIndex
                      ? 'bg-orange-600 text-white border-orange-600'
                      : 'bg-white text-gray-700 border-gray-300'
                  }`}
                >
                  #{layout.board_number}
                </button>
              ))}
            </div>

            {activeLayout && (
              <div className="space-y-4 border rounded-xl p-4">
                {renderLayout(activeLayout)}

                <div className="overflow-x-auto">
                  <table className="w-full text-sm border-collapse">
                    <thead className="bg-gray-50 border-b">
                      <tr>
                        <th className="px-3 py-2 text-left">#</th>
                        <th className="px-3 py-2 text-left">Label</th>
                        <th className="px-3 py-2 text-left">Size</th>
                        <th className="px-3 py-2 text-left">Rotated</th>
                        <th className="px-3 py-2 text-left">Position</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeLayout.panels.map((panel: any, idx: number) => (
                        <tr key={idx} className="border-b border-gray-100">
                          <td className="px-3 py-2">{idx + 1}</td>
                          <td className="px-3 py-2">{panel.label || `Panel ${panel.panel_index + 1}`}</td>
                          <td className="px-3 py-2">{panel.width} × {panel.length}</td>
                          <td className="px-3 py-2">{panel.rotated ? 'Yes' : 'No'}</td>
                          <td className="px-3 py-2">({panel.x}, {panel.y})</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {activeLayout.cuts?.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">
                      How to Cut — Board #{activeLayout.board_number}
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm border-collapse">
                        <thead className="bg-gray-50 border-b">
                          <tr>
                            <th className="px-3 py-2 text-left">Step</th>
                            <th className="px-3 py-2 text-left">Orientation</th>
                            <th className="px-3 py-2 text-left">Start</th>
                            <th className="px-3 py-2 text-left">End</th>
                            <th className="px-3 py-2 text-left">Length (mm)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activeLayout.cuts.map((cut: any, idx: number) => (
                            <tr key={idx} className="border-b border-gray-100">
                              <td className="px-3 py-2 font-semibold">{cut.sequence || cut.id}</td>
                              <td className="px-3 py-2">{cut.orientation === 'V' ? 'Vertical' : 'Horizontal'}</td>
                              <td className="px-3 py-2">({cut.x1}, {cut.y1})</td>
                              <td className="px-3 py-2">({cut.x2}, {cut.y2})</td>
                              <td className="px-3 py-2">{cut.length}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </Card>

      {results.boq?.items?.length > 0 && (
        <Card title="BOQ Items" hover>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">Description</th>
                  <th className="px-3 py-2 text-left">Size</th>
                  <th className="px-3 py-2 text-left">Qty</th>
                  <th className="px-3 py-2 text-left">Unit</th>
                  <th className="px-3 py-2 text-left">Edges</th>
                  <th className="px-3 py-2 text-left">Material</th>
                </tr>
              </thead>
              <tbody>
                {results.boq.items.map((item: any) => (
                  <tr key={item.item_no} className="border-b border-gray-100">
                    <td className="px-3 py-2">{item.item_no}</td>
                    <td className="px-3 py-2">{item.description}</td>
                    <td className="px-3 py-2">{item.size}</td>
                    <td className="px-3 py-2">{item.quantity}</td>
                    <td className="px-3 py-2">{item.unit}</td>
                    <td className="px-3 py-2">{item.edges}</td>
                    <td className="px-3 py-2">
                      {item.board_type || item.core_type} {item.thickness_mm}mm {item.company} {item.colour}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {results.boq?.pricing?.lines?.length > 0 && (
        <Card title="Pricing Summary" hover>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse mb-4">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-3 py-2 text-left">Item</th>
                  <th className="px-3 py-2 text-left">Description</th>
                  <th className="px-3 py-2 text-left">Qty</th>
                  <th className="px-3 py-2 text-left">Unit</th>
                  <th className="px-3 py-2 text-left">Unit Price</th>
                  <th className="px-3 py-2 text-left">Amount</th>
                </tr>
              </thead>
              <tbody>
                {results.boq.pricing.lines.map((line: any, idx: number) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="px-3 py-2">{line.item}</td>
                    <td className="px-3 py-2">{line.description}</td>
                    <td className="px-3 py-2">{line.quantity}</td>
                    <td className="px-3 py-2">{line.unit}</td>
                    <td className="px-3 py-2">{line.unit_price}</td>
                    <td className="px-3 py-2">{line.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 rounded bg-gray-50">
                <div className="text-sm text-gray-600">Subtotal</div>
                <div className="text-xl font-bold">{results.boq.pricing.subtotal}</div>
              </div>
              <div className="p-4 rounded bg-gray-50">
                <div className="text-sm text-gray-600">{results.boq.pricing.tax_name}</div>
                <div className="text-xl font-bold">{results.boq.pricing.tax_amount}</div>
              </div>
              <div className="p-4 rounded bg-gray-50">
                <div className="text-sm text-gray-600">Total</div>
                <div className="text-xl font-bold">{results.boq.pricing.total}</div>
              </div>
              <div className="p-4 rounded bg-gray-50">
                <div className="text-sm text-gray-600">Currency</div>
                <div className="text-xl font-bold">{results.boq.pricing.currency}</div>
              </div>
            </div>
          </div>
        </Card>
      )}

      {results.edging?.details?.length > 0 && (
        <Card title="Edging Details" hover>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-3 py-2 text-left">Panel</th>
                  <th className="px-3 py-2 text-left">Qty</th>
                  <th className="px-3 py-2 text-left">Edge / Panel (m)</th>
                  <th className="px-3 py-2 text-left">Total Edge (m)</th>
                  <th className="px-3 py-2 text-left">Applied Edges</th>
                </tr>
              </thead>
              <tbody>
                {results.edging.details.map((row: any, idx: number) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="px-3 py-2">{row.panel_label}</td>
                    <td className="px-3 py-2">{row.quantity}</td>
                    <td className="px-3 py-2">{row.edge_per_panel_m}</td>
                    <td className="px-3 py-2">{row.total_edge_m}</td>
                    <td className="px-3 py-2">{row.edges_applied}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {fullscreen && activeLayout && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-[95vw] h-[95vh] overflow-auto p-4 shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-gray-900">
                Fullscreen Board #{activeLayout.board_number}
              </h2>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={zoomOut}>Zoom -</Button>
                <Button variant="outline" size="sm" onClick={resetZoom}>Reset</Button>
                <Button variant="outline" size="sm" onClick={zoomIn}>Zoom +</Button>
                <Button onClick={() => setFullscreen(false)}>Close</Button>
              </div>
            </div>
            {renderLayout(activeLayout, true)}
          </div>
        </div>
      )}
    </div>
  );
}