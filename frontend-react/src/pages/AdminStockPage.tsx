import { useEffect, useMemo, useState } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { api } from '../api/client';
import type { BoardItem, StockTransaction } from '../types';

interface Props {
  onBack?: () => void;
}

const emptyForm = {
  board_type: '',
  thickness_mm: 18,
  color_name: '',
  company: '',
  width_mm: 1220,
  length_mm: 2440,
  price_per_board: 0,
  quantity: 0,
  low_stock_threshold: 3,
  is_active: true,
};

export default function AdminStockPage({ onBack }: Props) {
  const [items, setItems] = useState<BoardItem[]>([]);
  const [transactions, setTransactions] = useState<StockTransaction[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<any>(emptyForm);
  const [adjustQty, setAdjustQty] = useState('1');
  const [adjustNotes, setAdjustNotes] = useState('');
  const [search, setSearch] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    try {
      const data = await api.getBoardItems();
      setItems(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load boards');
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async () => {
    try {
      const created = await api.createBoardItem({
        ...form,
        thickness_mm: Number(form.thickness_mm),
        width_mm: Number(form.width_mm),
        length_mm: Number(form.length_mm),
        price_per_board: Number(form.price_per_board),
        quantity: Number(form.quantity),
        low_stock_threshold: Number(form.low_stock_threshold),
      });
      setItems((prev) => [...prev, created]);
      setForm(emptyForm);
      setMessage('Board item created');
      setError('');
    } catch (e: any) {
      setError(e.message || 'Failed to create');
    }
  };

  const handleAddStock = async (id: number) => {
    try {
      await api.addBoardStock({
        board_item_id: id,
        quantity: Number(adjustQty),
        notes: adjustNotes || undefined,
        reference: 'ADMIN_ADD_STOCK',
      });
      setMessage('Stock added');
      setAdjustQty('1');
      setAdjustNotes('');
      await load();
      if (selectedId === id) {
        setTransactions(await api.getBoardTransactions(id));
      }
    } catch (e: any) {
      setError(e.message || 'Failed to add stock');
    }
  };

  const openHistory = async (id: number) => {
    setSelectedId(id);
    setTransactions(await api.getBoardTransactions(id));
  };

  const filtered = useMemo(() => {
    return items.filter((i) =>
      `${i.board_type} ${i.thickness_mm} ${i.color_name} ${i.company} ${i.width_mm} ${i.length_mm}`
        .toLowerCase()
        .includes(search.toLowerCase())
    );
  }, [items, search]);

  return (
    <div className="p-6 max-w-[1800px] mx-auto space-y-6">
      <div className="flex justify-between items-start gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Admin Board Inventory</h1>
          <p className="text-gray-600 mt-2">Simple manual control for board stock and pricing.</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={api.openInventoryPdf}>Print Inventory PDF</Button>
          {onBack && <Button variant="outline" onClick={onBack}>Back</Button>}
        </div>
      </div>

      {message && <div className="p-3 rounded border border-green-200 bg-green-50 text-green-700">{message}</div>}
      {error && <div className="p-3 rounded border border-red-200 bg-red-50 text-red-700">{error}</div>}

      <Card title="Add Board Item" hover>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Input label="Board Type" value={form.board_type} onChange={(e) => setForm({ ...form, board_type: e.target.value })} />
          <Input label="Thickness (mm)" type="number" value={form.thickness_mm} onChange={(e) => setForm({ ...form, thickness_mm: Number(e.target.value) })} />
          <Input label="Color" value={form.color_name} onChange={(e) => setForm({ ...form, color_name: e.target.value })} />
          <Input label="Company" value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
          <Input label="Width (mm)" type="number" value={form.width_mm} onChange={(e) => setForm({ ...form, width_mm: Number(e.target.value) })} />
          <Input label="Length (mm)" type="number" value={form.length_mm} onChange={(e) => setForm({ ...form, length_mm: Number(e.target.value) })} />
          <Input label="Price Per Board" type="number" value={form.price_per_board} onChange={(e) => setForm({ ...form, price_per_board: Number(e.target.value) })} />
          <Input label="Opening Quantity" type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
          <Input label="Low Stock Threshold" type="number" value={form.low_stock_threshold} onChange={(e) => setForm({ ...form, low_stock_threshold: Number(e.target.value) })} />
        </div>
        <div className="mt-4 flex justify-end">
          <Button onClick={handleCreate}>Save Board Item</Button>
        </div>
      </Card>

      <Card title="Search / Inventory" hover>
        <Input label="Search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search board type, thickness, color, company..." />
      </Card>

      <Card title="Board Inventory" subtitle={`${filtered.length} items`} hover>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-3 py-2 text-left">Board</th>
                <th className="px-3 py-2 text-left">Size</th>
                <th className="px-3 py-2 text-left">Price</th>
                <th className="px-3 py-2 text-left">Qty</th>
                <th className="px-3 py-2 text-left">Low Stock</th>
                <th className="px-3 py-2 text-left">Quick Add</th>
                <th className="px-3 py-2 text-left">History</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={row.id} className="border-b border-gray-100">
                  <td className="px-3 py-2">{row.board_type} • {row.thickness_mm}mm • {row.color_name} • {row.company}</td>
                  <td className="px-3 py-2">{row.width_mm} × {row.length_mm}</td>
                  <td className="px-3 py-2">{row.price_per_board}</td>
                  <td className="px-3 py-2">{row.quantity}</td>
                  <td className="px-3 py-2">{row.low_stock_threshold}</td>
                  <td className="px-3 py-2">
                    <div className="flex gap-2">
                      <input className="w-20 border rounded px-2 py-1" type="number" min={1} value={adjustQty} onChange={(e) => setAdjustQty(e.target.value)} />
                      <Button size="sm" onClick={() => handleAddStock(row.id)}>Add</Button>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <Button size="sm" variant="outline" onClick={() => openHistory(row.id)}>History</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Adjustment Notes" hover>
        <Input label="Notes" value={adjustNotes} onChange={(e) => setAdjustNotes(e.target.value)} />
      </Card>

      <Card title="Transactions" hover>
        {!selectedId ? (
          <p className="text-gray-500">Select a board row to view transactions.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Qty</th>
                  <th className="px-3 py-2 text-left">Before</th>
                  <th className="px-3 py-2 text-left">After</th>
                  <th className="px-3 py-2 text-left">Reference</th>
                  <th className="px-3 py-2 text-left">Notes</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.id} className="border-b border-gray-100">
                    <td className="px-3 py-2">{new Date(tx.created_at).toLocaleString()}</td>
                    <td className="px-3 py-2">{tx.transaction_type}</td>
                    <td className="px-3 py-2">{tx.quantity}</td>
                    <td className="px-3 py-2">{tx.balance_before}</td>
                    <td className="px-3 py-2">{tx.balance_after}</td>
                    <td className="px-3 py-2">{tx.reference || '-'}</td>
                    <td className="px-3 py-2">{tx.notes || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}