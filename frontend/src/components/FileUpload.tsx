import { useState, useRef } from 'react';
import {
  Box,
  Button,
  Typography,
  LinearProgress,
  IconButton,
  Paper,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Collapse,
  Tooltip,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DeleteIcon from '@mui/icons-material/Delete';
import DescriptionIcon from '@mui/icons-material/Description';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

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
      } catch (err: any) {
        setError(err.message || 'Fehler beim Upload');
      }
    }

    setUploading(false);
    setUploadProgress('');
    fetchDocuments();

    // Reset input
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (filename: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setDocuments((prev) => prev.filter((d) => d.filename !== filename));
      }
    } catch {
      console.error('Fehler beim Löschen');
    }
  };

  return (
    <Paper
      elevation={0}
      sx={{
        mx: 2,
        mt: 1,
        mb: 1,
        backgroundColor: '#111111',
        borderRadius: 2,
        overflow: 'hidden',
      }}
    >
      {/* Header mit Toggle */}
      <Box
        onClick={handleToggle}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1,
          cursor: 'pointer',
          '&:hover': { backgroundColor: 'rgba(255,224,0,0.05)' },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <DescriptionIcon sx={{ fontSize: 18, color: '#ffe000' }} />
          <Typography variant="body2" sx={{ color: '#f6f6f6', fontWeight: 500 }}>
            Dokumente (RAG)
          </Typography>
          {documents.length > 0 && (
            <Chip
              label={documents.length}
              size="small"
              sx={{
                height: 20,
                fontSize: '0.7rem',
                backgroundColor: '#ffe000',
                color: '#000',
              }}
            />
          )}
        </Box>
        {expanded ? (
          <ExpandLessIcon sx={{ color: '#888', fontSize: 20 }} />
        ) : (
          <ExpandMoreIcon sx={{ color: '#888', fontSize: 20 }} />
        )}
      </Box>

      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          {/* Upload Button */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.csv,.json,.xml,.html"
            onChange={handleUpload}
            style={{ display: 'none' }}
            id="file-upload-input"
          />
          <label htmlFor="file-upload-input">
            <Button
              component="span"
              variant="outlined"
              startIcon={<CloudUploadIcon />}
              disabled={uploading}
              fullWidth
              sx={{
                mt: 1,
                borderColor: '#ffe000',
                color: '#ffe000',
                '&:hover': { borderColor: '#ffe000', backgroundColor: 'rgba(255,224,0,0.1)' },
              }}
            >
              {uploading ? 'Wird verarbeitet...' : 'Dokument hochladen'}
            </Button>
          </label>

          {/* Upload Fortschritt */}
          {uploading && (
            <Box sx={{ mt: 1 }}>
              <LinearProgress sx={{ '& .MuiLinearProgress-bar': { backgroundColor: '#ffe000' } }} />
              <Typography variant="caption" sx={{ color: '#aaa', mt: 0.5, display: 'block' }}>
                {uploadProgress}
              </Typography>
            </Box>
          )}

          {/* Fehler */}
          {error && (
            <Typography variant="caption" color="error" sx={{ mt: 1, display: 'block' }}>
              {error}
            </Typography>
          )}

          {/* Dokumentenliste */}
          {documents.length > 0 && (
            <List dense sx={{ mt: 1 }}>
              {documents.map((doc) => (
                <ListItem
                  key={doc.filename}
                  sx={{
                    backgroundColor: 'rgba(255,255,255,0.03)',
                    borderRadius: 1,
                    mb: 0.5,
                    pr: 6,
                  }}
                >
                  <UploadFileIcon sx={{ fontSize: 16, mr: 1, color: '#ffe000' }} />
                  <ListItemText
                    primary={doc.filename}
                    secondary={`${doc.chunks} Chunks`}
                    primaryTypographyProps={{ fontSize: '0.8rem', color: '#f6f6f6', noWrap: true }}
                    secondaryTypographyProps={{ fontSize: '0.7rem', color: '#888' }}
                  />
                  <ListItemSecondaryAction>
                    <Tooltip title="Löschen">
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => handleDelete(doc.filename)}
                        sx={{ color: 'rgba(255,255,255,0.4)' }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          )}

          {documents.length === 0 && !uploading && (
            <Typography variant="caption" sx={{ color: '#666', mt: 1, display: 'block', textAlign: 'center' }}>
              Keine Dokumente hochgeladen
            </Typography>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}
