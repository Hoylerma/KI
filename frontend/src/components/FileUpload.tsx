import { useState, useRef } from 'react';
import { FileText, Upload, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { API_BASE_URL } from '../api';

interface UploadedDoc {
  filename: string;
  chunks: number;
  uploaded_at: string;
}

export default function FileUpload() {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const [documents, setDocuments] = useState<UploadedDoc[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/documents`);
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch {
      console.error('Fehler beim Laden der Dokumente');
    }
  };

  
  const handleToggle = () => {
    if (!expanded) fetchDocuments();
    setExpanded(!expanded);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setError('');

    for (const file of Array.from(files)) {
      setUploadProgress(`Verarbeite: ${file.name}...`);
      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch(`${API_BASE_URL}/upload`, {
          method: 'POST',
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Upload fehlgeschlagen');
        }

        const result = await res.json();
        setUploadProgress(`${file.name}: ${result.chunks} Chunks erstellt`);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Fehler beim Upload');
      }
    }

    setUploading(false);
    setUploadProgress('');
    fetchDocuments();

    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (filename: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.filename !== filename));
      }
    } catch {
      console.error('Fehler beim Löschen');
    }
  };

  return (
    <div className="mx-2 mt-1 mb-1 bg-[#111111] rounded-lg overflow-hidden">
      {/* Header with toggle */}
      <button
        onClick={handleToggle}
        className="w-full flex items-center justify-between px-3 py-2 hover:bg-[#ffe000]/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-[#ffe000]" />
          <span className="text-[#f6f6f6] text-sm font-medium">Dokumente (RAG)</span>
          {documents.length > 0 && (
            <span className="bg-[#ffe000] text-black text-xs rounded-full px-1.5 py-0.5 leading-none font-medium">
              {documents.length}
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp size={16} className="text-[#888]" />
        ) : (
          <ChevronDown size={16} className="text-[#888]" />
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-3">
          {/* Upload button */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.csv,.json,.xml,.html"
            onChange={handleUpload}
            className="hidden"
            id="file-upload-input"
          />
          <label htmlFor="file-upload-input">
            <span
              className={[
                'mt-2 w-full flex items-center justify-center gap-2 border border-[#ffe000] text-[#ffe000] px-3 py-2 rounded text-sm cursor-pointer',
                uploading
                  ? 'opacity-50 cursor-not-allowed'
                  : 'hover:bg-[#ffe000]/10 transition-colors',
              ].join(' ')}
            >
              <Upload size={16} />
              {uploading ? 'Wird verarbeitet...' : 'Dokument hochladen'}
            </span>
          </label>

          {/* Progress */}
          {uploading && (
            <div className="mt-2">
              <div className="h-1 bg-[#333] rounded overflow-hidden">
                <div className="h-full bg-[#ffe000] animate-pulse w-full" />
              </div>
              {uploadProgress && (
                <p className="text-xs text-[#aaa] mt-1">{uploadProgress}</p>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-xs text-red-400 mt-2">{error}</p>
          )}
        
          {/* Document list */}
          
          {documents.length > 0 && (
            <ul className="mt-2 space-y-1">
              {documents.map(doc => (
                <li
                  key={doc.filename}
                  className="flex items-center gap-2 bg-white/[0.03] rounded px-2 py-1.5"
                >
                  <Upload size={14} className="text-[#ffe000] flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-[#f6f6f6] truncate">{doc.filename}</p>
                    <p className="text-xs text-[#888]">{doc.chunks} Chunks</p>
                  </div>
                  <button
                    onClick={() => handleDelete(doc.filename)}
                    className="p-1 text-white/40 hover:text-white/80 transition-colors flex-shrink-0"
                    title="Löschen"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          

          {documents.length === 0 && !uploading && (
            <p className="text-xs text-[#666] mt-2 text-center">
              Keine Dokumente hochgeladen
            </p>
          )}
        </div>
      )}
    </div>
  );
}
