/**
 * SavedTablesList - OneDrive/Office 365 style table list
 */

import { useState } from 'react';
import { Download, Trash2, FileSpreadsheet, MoreVertical, Search } from 'lucide-react';
import excelIcon from '../../assets/table-logos/excel.png';
import csvIcon from '../../assets/table-logos/csv.png';

interface SavedTable {
  id: string;
  name: string;
  description?: string;
  file_name: string;
  created_at: string;
  row_count: number;
  column_count: number;
}

interface SavedTablesListProps {
  tables: SavedTable[];
  onImport: (tableId: string) => void;
  onDelete?: (tableId: string) => void;
  isLoading?: boolean;
}

export default function SavedTablesList({
  tables,
  onImport,
  onDelete,
  isLoading = false,
}: SavedTablesListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const filteredTables = tables.filter(table =>
    table.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (table.description && table.description.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Get file icon based on file extension
  const getFileIcon = (fileName: string) => {
    const ext = fileName.toLowerCase().split('.').pop();
    if (ext === 'csv') {
      return csvIcon;
    }
    return excelIcon; // xlsx, xls default to Excel icon
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          placeholder="Search tables..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
        />
      </div>

      {/* Tables List - OneDrive Style */}
      {filteredTables.length === 0 ? (
        <div className="text-center py-12">
          <FileSpreadsheet size={48} className="mx-auto text-slate-300 mb-3" />
          <p className="text-slate-600 font-medium">No saved tables found</p>
          <p className="text-sm text-slate-500 mt-1">
            {searchQuery ? 'Try a different search term' : 'Upload and save your first table to get started'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto overflow-y-visible">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider w-2/5">
                  Name
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider w-1/6">
                  Opened
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider w-1/6">
                  Owner
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider w-1/4">
                  Activity
                </th>
                <th className="w-12"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredTables.map((table) => (
                <tr
                  key={table.id}
                  className="hover:bg-slate-50 cursor-pointer group transition-colors"
                  onClick={() => onImport(table.id)}
                >
                  {/* Name Column */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <img src={getFileIcon(table.file_name)} alt="File icon" className="w-8 h-8" />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm text-slate-900 font-medium truncate">
                          {table.name}
                        </div>
                        <div className="text-xs text-slate-500 truncate">
                          {table.description || `${table.row_count} rows × ${table.column_count} cols`}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Opened Column */}
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {formatTimeAgo(table.created_at)}
                  </td>

                  {/* Owner Column */}
                  <td className="px-4 py-3 text-sm text-slate-600">
                    You
                  </td>

                  {/* Activity Column */}
                  <td className="px-4 py-3 text-sm text-slate-600">
                    Edited {formatTimeAgo(table.created_at)}
                  </td>

                  {/* Actions Column */}
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenMenu(openMenu === table.id ? null : table.id);
                      }}
                      className="p-1.5 hover:bg-slate-200 rounded-md transition-colors opacity-0 group-hover:opacity-100 relative"
                      id={`menu-button-${table.id}`}
                    >
                      <MoreVertical size={16} className="text-slate-600" />
                    </button>

                    {openMenu === table.id && (
                      <>
                        <div
                          className="fixed inset-0 z-10"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenMenu(null);
                          }}
                        />
                        <div
                          className="fixed w-48 bg-white border border-slate-200 rounded-lg shadow-xl z-20 py-1"
                          style={{
                            top: `${document.getElementById(`menu-button-${table.id}`)?.getBoundingClientRect().bottom ?? 0}px`,
                            left: `${(document.getElementById(`menu-button-${table.id}`)?.getBoundingClientRect().right ?? 0) - 192}px`,
                          }}
                        >
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onImport(table.id);
                                setOpenMenu(null);
                              }}
                              className="w-full px-3 py-2 text-left text-sm hover:bg-slate-100 flex items-center gap-2 text-slate-700"
                            >
                              <Download size={14} />
                              Import Table
                            </button>
                            {onDelete && (
                              <>
                                <div className="border-t border-slate-200 my-1" />
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (confirm(`Delete table "${table.name}"?`)) {
                                      onDelete(table.id);
                                    }
                                    setOpenMenu(null);
                                  }}
                                  className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                                >
                                  <Trash2 size={14} />
                                  Delete Table
                                </button>
                              </>
                            )}
                          </div>
                        </>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
