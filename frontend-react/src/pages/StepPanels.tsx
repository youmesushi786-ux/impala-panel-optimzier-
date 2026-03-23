import { useState, useEffect, useMemo } from 'react';
import { Trash2, Check, Settings } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Toggle } from '../components/ui/Toggle';
import { Chip } from '../components/ui/Chip';
import { api } from '../api/client';
import type {
  Panel,
  BoardSelection,
  PanelEdges,
  OptimizationOptions,
  CustomerDetails,
  BoardCatalog,
  BoardItem,
} from '../types';

interface StepPanelsProps {
  panels: Panel[];
  onPanelsChange: (panels: Panel[]) => void;
  options: OptimizationOptions;
  onOptionsChange: (options: OptimizationOptions) => void;
  customer: CustomerDetails;
  onCustomerChange: (customer: CustomerDetails) => void;
  onNext: () => void;
  onOpenAdminStock: () => void;
}

export function StepPanels({
  panels,
  onPanelsChange,
  options,
  onOptionsChange,
  customer,
  onCustomerChange,
  onNext,
  onOpenAdminStock,
}: StepPanelsProps) {
  const [catalog, setCatalog] = useState<BoardCatalog | null>(null);
  const [panelForm, setPanelForm] = useState({
    label: '',
    width: '',
    length: '',
    quantity: '1',
    notes: '',
    alignment: 'none' as 'none' | 'horizontal' | 'vertical',
  });
  const [selectedBoard, setSelectedBoard] = useState<BoardItem | null>(null);
  const [edgesForm, setEdgesForm] = useState<PanelEdges>({
    top: false,
    right: false,
    bottom: false,
    left: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saveMessage, setSaveMessage] = useState('');

  useEffect(() => {
    api.getBoardCatalog().then(setCatalog).catch(() => {});
  }, []);

  const availableBoards = useMemo(() => catalog?.items ?? [], [catalog]);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!panelForm.label.trim()) e.label = 'Label required';
    if (!panelForm.width || Number(panelForm.width) <= 0) e.width = 'Width required';
    if (!panelForm.length || Number(panelForm.length) <= 0) e.length = 'Length required';
    if (!panelForm.quantity || Number(panelForm.quantity) <= 0) e.quantity = 'Quantity required';
    if (!selectedBoard) e.board = 'Board selection required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSavePanel = () => {
    if (!validate()) return;

    const board: BoardSelection = {
      board_item_id: selectedBoard!.id,
      board_type: selectedBoard!.board_type,
      thickness_mm: selectedBoard!.thickness_mm,
      company: selectedBoard!.company,
      color_name: selectedBoard!.color_name,
      width_mm: selectedBoard!.width_mm,
      length_mm: selectedBoard!.length_mm,
      price_per_board: selectedBoard!.price_per_board,
    };

    const newPanel: Panel = {
      id: Date.now().toString(),
      label: panelForm.label.trim(),
      width: Number(panelForm.width),
      length: Number(panelForm.length),
      quantity: Number(panelForm.quantity),
      alignment: panelForm.alignment,
      notes: panelForm.notes || undefined,
      board,
      edges: { ...edgesForm },
    };

    onPanelsChange([...panels, newPanel]);

    setPanelForm({
      label: '',
      width: '',
      length: '',
      quantity: '1',
      notes: '',
      alignment: 'none',
    });
    setSelectedBoard(null);
    setEdgesForm({ top: false, right: false, bottom: false, left: false });
    setErrors({});
    setSaveMessage('Panel saved.');
    setTimeout(() => setSaveMessage(''), 2000);
  };

  return (
    <div className="p-3 sm:p-4 lg:p-6 max-w-[1800px] mx-auto">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-2">
            Panels & Board Configuration
          </h2>
          <p className="text-sm sm:text-base text-gray-600">
            Choose one board item directly from admin stock and save the panel.
          </p>
        </div>

        <Button variant="outline" type="button" onClick={onOpenAdminStock} className="w-full sm:w-auto">
          <Settings className="w-4 h-4 mr-2" />
          Admin / Stock
        </Button>
      </div>

      <Card title="Add a Panel" subtitle="Panel details + board selection + edges" hover>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
          <div className="space-y-4">
            <Input
              label="Label"
              value={panelForm.label}
              onChange={(e) => setPanelForm({ ...panelForm, label: e.target.value })}
              error={errors.label}
            />

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Length (mm)"
                type="number"
                value={panelForm.length}
                onChange={(e) => setPanelForm({ ...panelForm, length: e.target.value })}
                error={errors.length}
              />
              <Input
                label="Width (mm)"
                type="number"
                value={panelForm.width}
                onChange={(e) => setPanelForm({ ...panelForm, width: e.target.value })}
                error={errors.width}
              />
            </div>

            <Input
              label="Quantity"
              type="number"
              value={panelForm.quantity}
              onChange={(e) => setPanelForm({ ...panelForm, quantity: e.target.value })}
              error={errors.quantity}
            />

            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Grain Alignment</p>
              <div className="flex flex-wrap gap-2">
                {(['none', 'horizontal', 'vertical'] as const).map((alignment) => (
                  <Chip
                    key={alignment}
                    label={alignment}
                    selected={panelForm.alignment === alignment}
                    onClick={() => setPanelForm({ ...panelForm, alignment })}
                  />
                ))}
              </div>
            </div>

            <Input
              label="Notes"
              value={panelForm.notes}
              onChange={(e) => setPanelForm({ ...panelForm, notes: e.target.value })}
            />
          </div>

          <div className="space-y-4 min-w-0">
            <h3 className="text-sm font-semibold text-gray-800">Board Selection</h3>

            {errors.board && (
              <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">
                {errors.board}
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {availableBoards.map((item) => (
                <Chip
                  key={item.id}
                  label={`${item.board_type} • ${item.thickness_mm}mm • ${item.color_name} • ${item.company} • ${item.width_mm}x${item.length_mm}`}
                  selected={selectedBoard?.id === item.id}
                  onClick={() => setSelectedBoard(item)}
                />
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-800">Edges</h3>

            <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
              {(['top', 'right', 'bottom', 'left'] as const).map((edge) => (
                <button
                  key={edge}
                  type="button"
                  onClick={() => setEdgesForm({ ...edgesForm, [edge]: !edgesForm[edge] })}
                  className={`px-3 py-2 rounded-lg border-2 font-medium text-sm text-left ${
                    edgesForm[edge]
                      ? 'border-orange-600 bg-orange-50 text-orange-700'
                      : 'border-gray-200 bg-white text-gray-600'
                  }`}
                >
                  {edgesForm[edge] && <Check className="inline w-4 h-4 mr-1" />}
                  {edge.charAt(0).toUpperCase() + edge.slice(1)}
                </button>
              ))}
            </div>

            <Button fullWidth size="lg" type="button" onClick={handleSavePanel}>
              Save Panel & Add Next
            </Button>

            {saveMessage && <p className="text-green-600 text-sm">{saveMessage}</p>}
          </div>
        </div>
      </Card>

      <Card title="Panels in this Job" hover className="mt-6">
        {panels.length === 0 ? (
          <p className="text-gray-500 text-sm sm:text-base">No panels saved yet.</p>
        ) : (
          <>
            {/* Mobile cards */}
            <div className="space-y-3 md:hidden">
              {panels.map((panel) => {
                const edgesLabel =
                  Object.entries(panel.edges)
                    .filter(([, v]) => v)
                    .map(([k]) => k[0].toUpperCase())
                    .join('') || 'None';

                return (
                  <div key={panel.id} className="border border-gray-200 rounded-xl p-4 bg-white">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold text-gray-900 break-words">{panel.label}</p>
                        <p className="text-sm text-gray-600">
                          {panel.length} × {panel.width} mm
                        </p>
                        <p className="text-sm text-gray-600">Qty: {panel.quantity}</p>
                      </div>

                      <button
                        onClick={() => onPanelsChange(panels.filter((p) => p.id !== panel.id))}
                        type="button"
                        className="shrink-0"
                      >
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </button>
                    </div>

                    <div className="mt-3 text-sm text-gray-700 break-words">
                      <p>
                        <span className="font-medium">Board:</span> {panel.board.board_type} •{' '}
                        {panel.board.thickness_mm}mm • {panel.board.color_name} •{' '}
                        {panel.board.company}
                      </p>
                      <p className="mt-1">
                        <span className="font-medium">Edges:</span> {edgesLabel}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm border-collapse min-w-[700px]">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-3 py-2 text-left">Label</th>
                    <th className="px-3 py-2 text-left">Size</th>
                    <th className="px-3 py-2 text-left">Qty</th>
                    <th className="px-3 py-2 text-left">Board</th>
                    <th className="px-3 py-2 text-left">Edges</th>
                    <th className="px-3 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {panels.map((panel) => {
                    const edgesLabel =
                      Object.entries(panel.edges)
                        .filter(([, v]) => v)
                        .map(([k]) => k[0].toUpperCase())
                        .join('') || 'None';

                    return (
                      <tr key={panel.id} className="border-b border-gray-100">
                        <td className="px-3 py-2">{panel.label}</td>
                        <td className="px-3 py-2">
                          {panel.length} × {panel.width}
                        </td>
                        <td className="px-3 py-2">{panel.quantity}</td>
                        <td className="px-3 py-2">
                          {panel.board.board_type} • {panel.board.thickness_mm}mm •{' '}
                          {panel.board.color_name} • {panel.board.company}
                        </td>
                        <td className="px-3 py-2">{edgesLabel}</td>
                        <td className="px-3 py-2 text-right">
                          <button
                            onClick={() => onPanelsChange(panels.filter((p) => p.id !== panel.id))}
                            type="button"
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>

      <Card title="Options" hover className="mt-6">
        <div className="space-y-3">
          <Input
            label="Kerf (mm)"
            type="number"
            value={options.kerf}
            onChange={(e) => onOptionsChange({ ...options, kerf: Number(e.target.value) })}
          />
          <Toggle
            label="Labels on panels"
            checked={options.labels_on_panels}
            onChange={(v) => onOptionsChange({ ...options, labels_on_panels: v })}
          />
          <Toggle
            label="Use single sheet"
            checked={options.use_single_sheet}
            onChange={(v) => onOptionsChange({ ...options, use_single_sheet: v })}
          />
          <Toggle
            label="Consider material"
            checked={options.consider_material}
            onChange={(v) => onOptionsChange({ ...options, consider_material: v })}
          />
          <Toggle
            label="Edge banding"
            checked={options.edge_banding}
            onChange={(v) => onOptionsChange({ ...options, edge_banding: v })}
          />
          <Toggle
            label="Consider grain"
            checked={options.consider_grain}
            onChange={(v) => onOptionsChange({ ...options, consider_grain: v })}
          />
        </div>
      </Card>

      <Card title="Customer Details" hover className="mt-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input
            label="Project Name"
            value={customer.project_name}
            onChange={(e) => onCustomerChange({ ...customer, project_name: e.target.value })}
          />
          <Input
            label="Customer Name"
            value={customer.customer_name}
            onChange={(e) => onCustomerChange({ ...customer, customer_name: e.target.value })}
          />
          <div className="md:col-span-2">
            <Input
              label="Notes"
              value={customer.notes}
              onChange={(e) => onCustomerChange({ ...customer, notes: e.target.value })}
            />
          </div>
        </div>
      </Card>

      <div className="mt-8">
        <Button onClick={onNext} size="lg" className="w-full sm:w-auto sm:min-w-[240px]">
          Optimize & View Results
        </Button>
      </div>
    </div>
  );
}
