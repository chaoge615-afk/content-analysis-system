interface ResultTableProps {
  data: any[];
}

export default function ResultTable({ data }: ResultTableProps) {
  if (!data || data.length === 0) {
    return <p className="text-gray-500">暂无数据</p>;
  }

  const columns = Object.keys(data[0]);

  return (
    <div className="overflow-x-auto border border-gray-200 rounded-lg">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {columns.map((column) => (
              <th
                key={column}
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {data.map((row, rowIndex) => (
            <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              {columns.map((column) => (
                <td
                  key={column}
                  className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                >
                  {String(row[column] ?? '-')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
