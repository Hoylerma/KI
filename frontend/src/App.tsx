import { useState, useEffect, useRef } from 'react';
import { 
  Box, 
  Paper, 
  CircularProgress,
  TextField,
  IconButton,
  Divider,
  Alert,
  Typography,
  Drawer,
  Button,
  List,
  ListItem,
  ListItemButton,
  ListItemText
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import PersonIcon from '@mui/icons-material/Person';
import MenuIcon from '@mui/icons-material/Menu';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import HistoryIcon from '@mui/icons-material/History';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
}

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
}

function App() {
  const [status, setStatus] = useState<string>('Verbinde...');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [input, setInput] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/')
      .then(res => res.json())
      .then(data => setStatus(data.status))
      .catch(() => setStatus('Backend nicht erreichbar'));
    
    // Neue Konversation starten
    startNewConversation();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentConversationId]);

  const currentMessages = currentConversationId 
    ? conversations.find(c => c.id === currentConversationId)?.messages || []
    : [];

  const startNewConversation = () => {
    const newConversation: Conversation = {
      id: Date.now().toString(),
      title: 'Neue Konversation',
      messages: [],
      createdAt: new Date(),
    };
    setConversations(prev => [newConversation, ...prev]);
    setCurrentConversationId(newConversation.id);
  };

  const deleteConversation = (id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
    if (currentConversationId === id) {
      const remaining = conversations.filter(c => c.id !== id);
      setCurrentConversationId(remaining[0]?.id || null);
    }
  };

  const selectConversation = (id: string) => {
    setCurrentConversationId(id);
  };

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentConversationId) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: input,
      sender: 'user',
      timestamp: new Date(),
    };
    
    setConversations(prev => prev.map(c => 
      c.id === currentConversationId 
        ? {
            ...c,
            messages: [...c.messages, userMessage],
            title: c.messages.length === 0 ? input.substring(0, 30) + '...' : c.title
          }
        : c
    ));
    
    setInput('');
    setLoading(true);
    setError('');

    try {
      const response = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: input }),
      });

      const data = await response.json();

      if (data.error) {
        setError(data.error);
      } else {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          text: data.response,
          sender: 'assistant',
          timestamp: new Date(),
        };
        
        setConversations(prev => prev.map(c =>
          c.id === currentConversationId
            ? { ...c, messages: [...c.messages, assistantMessage] }
            : c
        ));
      }
    } catch (err) {
      setError('Fehler beim Senden der Nachricht');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh', backgroundColor: '#fff' }}>
      {/* Left Sidebar - Hidden on mobile, collapsible on tablet */}
      <Drawer
        variant={window.innerWidth < 900 ? 'temporary' : 'permanent'}
        onClose={() => setSidebarOpen(false)}
        open={sidebarOpen}
        sx={{
          width: { xs: 0, sm: 0, md: 0, lg: 280 },
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: { xs: 280, sm: 280, md: 280, lg: 280 },
            boxSizing: 'border-box',
            backgroundColor: '#1a1a2e',
            color: '#fff',
            zIndex: 100,
            borderRight: '1px solid rgba(212, 175, 55, 0.2)'
          },
        }}
      >
        {/* Sidebar Header */}
        <Box sx={{ p: 2 }}>
          <Button
            fullWidth
            variant="contained"
            startIcon={<AddIcon />}
            onClick={startNewConversation}
            sx={{
              background: 'linear-gradient(135deg, #d4af37 0%, #f4d03f 100%)',
              color: '#1a1a2e',
              fontWeight: 600,
              textTransform: 'none',
              fontSize: '0.95rem',
              '&:hover': {
                boxShadow: '0 4px 15px rgba(212, 175, 55, 0.3)',
              }
            }}
          >
            Neuer Chat
          </Button>
        </Box>

        <Divider sx={{ borderColor: 'rgba(255,255,255,0.2)' }} />

        {/* Conversations List */}
        <Box sx={{ 
          flexGrow: 1, 
          overflowY: 'auto',
          px: 1,
          py: 2,
          '&::-webkit-scrollbar': {
            width: '6px',
          },
          '&::-webkit-scrollbar-track': {
            background: 'rgba(255,255,255,0.1)',
          },
          '&::-webkit-scrollbar-thumb': {
            background: '#d4af37',
            borderRadius: '3px',
          }
        }}>
          {conversations.length === 0 ? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <HistoryIcon sx={{ fontSize: 32, opacity: 0.5, mb: 1 }} />
              <Typography variant="caption" sx={{ opacity: 0.7 }}>
                Keine Chats
              </Typography>
            </Box>
          ) : (
            <List sx={{ py: 0 }}>
              {conversations.map((conv) => (
                <ListItem
                  key={conv.id}
                  disablePadding
                  secondaryAction={
                    <IconButton
                      edge="end"
                      size="small"
                      onClick={() => deleteConversation(conv.id)}
                      sx={{ color: '#fff', '&:hover': { color: '#d4af37' } }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  }
                  sx={{ mb: 1 }}
                >
                  <ListItemButton
                    selected={currentConversationId === conv.id}
                    onClick={() => selectConversation(conv.id)}
                    sx={{
                      borderRadius: 1,
                      backgroundColor: currentConversationId === conv.id ? 'rgba(212, 175, 55, 0.2)' : 'transparent',
                      '&:hover': {
                        backgroundColor: 'rgba(212, 175, 55, 0.15)',
                      },
                      '&.Mui-selected': {
                        backgroundColor: 'rgba(212, 175, 55, 0.2)',
                        '&:hover': {
                          backgroundColor: 'rgba(212, 175, 55, 0.25)',
                        }
                      }
                    }}
                  >
                    <ListItemText
                      primary={conv.title}
                      primaryTypographyProps={{
                        variant: 'body2',
                        sx: { fontSize: '0.9rem', fontWeight: 500 }
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
          )}
        </Box>

        {/* Sidebar Footer */}
        <Divider sx={{ borderColor: 'rgba(255,255,255,0.2)' }} />
        <Box sx={{ p: 2 }}>
          <Typography variant="caption" sx={{ opacity: 0.7, display: 'block', textAlign: 'center' }}>
            Status: {status}
          </Typography>
        </Box>
      </Drawer>

      {/* Mobile Menu Button */}
      <Box sx={{ 
        display: { xs: 'flex', sm: 'flex', md: 'none', lg: 'none' }, 
        position: 'absolute', 
        top: 20, 
        left: 20, 
        zIndex: 101 
      }}>
        <IconButton 
          onClick={() => setSidebarOpen(!sidebarOpen)} 
          sx={{ 
            color: '#1a1a2e',
            backgroundColor: 'rgba(212, 175, 55, 0.1)',
            '&:hover': { backgroundColor: 'rgba(212, 175, 55, 0.2)' }
          }}
        >
          <MenuIcon />
        </IconButton>
      </Box>

      {/* Main Chat Area */}
      <Box sx={{ 
        flexGrow: 1, 
        display: 'flex', 
        flexDirection: 'column',
        backgroundColor: '#fff',
        width: '100%'
      }}>
        {/* Chat Messages */}
        <Box
          sx={{
            flexGrow: 1,
            overflowY: 'auto',
            p: { xs: 1.5, sm: 2, md: 3 },
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            '&::-webkit-scrollbar': {
              width: '8px',
            },
            '&::-webkit-scrollbar-track': {
              background: '#f5f5f5',
            },
            '&::-webkit-scrollbar-thumb': {
              background: '#d4af37',
              borderRadius: '4px',
              '&:hover': { background: '#c9a227' }
            }
          }}
        >
          {currentMessages.length === 0 && (
            <Box sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: 2
            }}>
              <Box sx={{
                width: 120,
                height: 120,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #d4af37 0%, #f4d03f 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 8px 30px rgba(212, 175, 55, 0.3)',
                animation: 'pulse 2s ease-in-out infinite'
              }}>
                <SmartToyIcon sx={{ fontSize: 60, color: '#1a1a2e' }} />
              </Box>
              <Typography variant="h4" sx={{ color: '#333', textAlign: 'center', fontWeight: 600 }}>
                Bw-I Chatbot
              </Typography>
              <Typography variant="h6" sx={{ color: '#666', textAlign: 'center', fontWeight: 400 }}>
                Wie kann ich dir heute helfen?
              </Typography>
            </Box>
          )}

          {currentMessages.map((message) => (
            <Box
              key={message.id}
              sx={{
                display: 'flex',
                justifyContent: message.sender === 'user' ? 'flex-end' : 'flex-start',
                animation: 'slideIn 0.3s ease-out',
                '@keyframes slideIn': {
                  from: {
                    opacity: 0,
                    transform: message.sender === 'user' ? 'translateX(20px)' : 'translateX(-20px)'
                  },
                  to: {
                    opacity: 1,
                    transform: 'translateX(0)'
                  }
                }
              }}
            >
              <Box sx={{ display: 'flex', gap: 1.5, maxWidth: { xs: '95%', sm: '85%', md: '70%' }, alignItems: 'flex-start' }}>
                {message.sender === 'assistant' && (
                  <Box sx={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #d4af37 0%, #f4d03f 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: 0.5
                  }}>
                    <SmartToyIcon sx={{ fontSize: 16, color: '#1a1a2e' }} />
                  </Box>
                )}

                <Paper
                  elevation={message.sender === 'user' ? 1 : 0}
                  sx={{
                    p: 2,
                    backgroundColor: message.sender === 'user'
                      ? 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)'
                      : '#f5f5f5',
                    color: message.sender === 'user' ? '#fff' : '#333',
                    borderRadius: 2,
                    wordWrap: 'break-word',
                    whiteSpace: 'pre-wrap',
                    border: message.sender === 'assistant' ? '1px solid #e0e0e0' : 'none'
                  }}
                >
                  <Typography variant="body2" sx={{ lineHeight: 1.6 }}>
                    {message.text}
                  </Typography>
                </Paper>

                {message.sender === 'user' && (
                  <Box sx={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: '#e0e0e0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: 0.5
                  }}>
                    <PersonIcon sx={{ fontSize: 16, color: '#666' }} />
                  </Box>
                )}
              </Box>
            </Box>
          ))}

          {loading && (
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              animation: 'slideIn 0.3s ease-out'
            }}>
              <Box sx={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #d4af37 0%, #f4d03f 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <CircularProgress size={20} sx={{ color: '#1a1a2e' }} />
              </Box>
              <Typography variant="body2" sx={{ color: '#999', fontStyle: 'italic' }}>
                Denke nach...
              </Typography>
            </Box>
          )}

          {error && (
            <Alert severity="error" sx={{ borderRadius: 2, animation: 'slideIn 0.3s ease-out' }}>
              {error}
            </Alert>
          )}

          <div ref={messagesEndRef} />
        </Box>

        {/* Input Area */}
        <Box sx={{
          p: { xs: 1.5, sm: 2, md: 3 },
          backgroundColor: '#fff',
          borderTop: '1px solid #e0e0e0'
        }}>
          <form onSubmit={sendMessage}>
            <Box sx={{
              display: 'flex',
              gap: 1.5,
              maxWidth: '100%'
            }}>
              <TextField
                fullWidth
                placeholder="Schreibe deine Nachricht hier..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={loading || !currentConversationId}
                multiline
                maxRows={4}
                minRows={1}
                variant="outlined"
                autoFocus
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 2,
                    backgroundColor: '#f5f7fa',
                    fontSize: { xs: '0.9rem', sm: '1rem' },
                    '&:hover fieldset': {
                      borderColor: '#d4af37',
                    },
                    '&.Mui-focused fieldset': {
                      borderColor: '#d4af37',
                      borderWidth: 2
                    }
                  }
                }}
              />
              <IconButton
                type="submit"
                disabled={loading || !input.trim() || !currentConversationId}
                sx={{
                  background: 'linear-gradient(135deg, #d4af37 0%, #f4d03f 100%)',
                  color: '#1a1a2e',
                  width: 48,
                  height: 48,
                  borderRadius: 2,
                  boxShadow: '0 4px 15px rgba(212, 175, 55, 0.3)',
                  '&:hover': {
                    boxShadow: '0 6px 20px rgba(212, 175, 55, 0.4)',
                    transform: 'translateY(-2px)',
                    transition: 'all 0.2s ease'
                  },
                  '&:disabled': {
                    background: '#e0e0e0',
                    color: '#999',
                    boxShadow: 'none'
                  },
                  transition: 'all 0.2s ease'
                }}
              >
                <SendIcon />
              </IconButton>
            </Box>
          </form>
        </Box>
      </Box>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.8; }
        }
        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </Box>
  );
}

export default App;
