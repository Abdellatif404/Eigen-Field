import { useState, useEffect, useRef } from 'react';

import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';

import { DashboardContent } from 'src/layouts/dashboard';

import { Iconify } from 'src/components/iconify';
import { Scrollbar } from 'src/components/scrollbar';

import { ChatInput } from '../chat-input';
import { ChatMessage } from '../chat-message';
import { DocumentList } from '../document-list';
import { UploadDialog } from '../upload-dialog';
import { TypingIndicator } from '../typing-indicator';

// ----------------------------------------------------------------------

const SOURCES_DELIMITER = '\n<!--SOURCES_JSON-->';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  timestamp: string;
};

type Document = {
  internal_id: string;
  filename: string;
  uploadDate: string;
  chunks?: number;
};

export function ChatView() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await fetch('http://127.0.0.1:9000/documents');
      if (response.ok) {
        const data = await response.json();

        const formattedDocs = data.documents.map((rawName: string) => {
          const firstUnderscoreIndex = rawName.indexOf('_');
          const id = rawName.substring(0, firstUnderscoreIndex);
          const name = rawName.substring(firstUnderscoreIndex + 1);

          return {
            internal_id: id,
            filename: name,
            uploadDate: new Date().toLocaleDateString(),
            chunks: 0,
          };
        });

        setDocuments(formattedDocs);
      }
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    }
  };

  const handleSend = async (content: string) => {
    if (!content.trim()) return;

    const now = Date.now();
    const userMsgId = `u-${now}`;
    const assistantMsgId = `a-${now}`;

    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        content,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);

    setLoading(true);
    setIsTyping(true);

    try {
      const response = await fetch(
        `http://127.0.0.1:9000/chat?query=${encodeURIComponent(
          content
        )}&top_k=5`,
        { method: 'POST' }
      );

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = '';
      let assistantMessageAdded = false;
      let rafId: number | null = null;

      const getDisplayText = (text: string) => {
        const delimiterIndex = text.indexOf(SOURCES_DELIMITER);
        return delimiterIndex !== -1 ? text.substring(0, delimiterIndex) : text;
      };

      const parseSources = (text: string): string[] => {
        const delimiterIndex = text.indexOf(SOURCES_DELIMITER);
        if (delimiterIndex === -1) return [];
        try {
          const jsonStr = text.substring(delimiterIndex + SOURCES_DELIMITER.length);
          const sources = JSON.parse(jsonStr) as { source: string; page: number | null }[];
          return sources.map(
            (s) => `${s.source}${s.page ? ` (p. ${s.page})` : ''}`
          );
        } catch {
          return [];
        }
      };

      const scheduleUpdate = () => {
        if (rafId) return;

        rafId = requestAnimationFrame(() => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? { ...msg, content: getDisplayText(accumulatedText) }
                : msg
            )
          );
          rafId = null;
        });
      };

      while (true) {
        const { value, done } = await reader.read();

        if (done) {
          if (rafId) cancelAnimationFrame(rafId);
          const sources = parseSources(accumulatedText);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMsgId
                ? {
                    ...msg,
                    content: getDisplayText(accumulatedText),
                    sources,
                    timestamp: new Date().toLocaleTimeString(),
                  }
                : msg
            )
          );
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        accumulatedText += chunk;

        if (!assistantMessageAdded && accumulatedText.trim().length > 0) {
          setIsTyping(false);
          setMessages((prev) => [
            ...prev,
            {
              id: assistantMsgId,
              role: 'assistant',
              content: getDisplayText(accumulatedText),
              timestamp: new Date().toLocaleTimeString(),
            },
          ]);
          assistantMessageAdded = true;
        } else if (assistantMessageAdded) {
          scheduleUpdate();
        }
      }
    } catch (error) {
      console.error('Streaming error:', error);
      setIsTyping(false);

      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: 'assistant',
          content: 'Sorry, there was an error generating the response.',
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } finally {
      setLoading(false);
      setIsTyping(false);
    }
  };

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', 'http://127.0.0.1:9000/upload', true);

      xhr.onload = () => {
        if (xhr.status === 200) {
          const data = JSON.parse(xhr.responseText);

          const newDoc: Document = {
            internal_id: data.internal_id,
            filename: data.filename,
            uploadDate: new Date().toLocaleDateString(),
            chunks: data.indexing_summary,
          };

          setDocuments((prev) => [...prev, newDoc]);
          resolve();
        } else {
          reject(new Error('Upload failed'));
        }
      };

      xhr.onerror = () => reject(new Error('Network error'));
      xhr.send(formData);
    });
  };

  const handleDelete = async (filename: string) => {
    const docToDelete = documents.find((d) => d.filename === filename);
    if (!docToDelete) return;

    setDeleting(filename);
    try {
      const response = await fetch(
        `http://127.0.0.1:9000/documents/${docToDelete.internal_id}`,
        {
          method: 'DELETE',
        }
      );

      if (response.ok) {
        setDocuments((prev) =>
          prev.filter((doc) => doc.internal_id !== docToDelete.internal_id)
        );
      }
    } catch (error) {
      console.error('Delete error:', error);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <DashboardContent maxWidth='xl'>
      <Typography variant='h4' sx={{ mb: 3, fontWeight: 600 }}>
        AI Agriculture Assistant
      </Typography>

      <Box
        sx={{
          height: 'calc(100vh - 160px)',
          overflow: 'hidden',
          pb: 2,
        }}
      >
        <Grid container spacing={3} sx={{ height: '100%' }}>
          {/* Chat Area */}
          <Grid size={{ xs: 12, md: 8 }}>
            <Box
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                gap: 1,
              }}
            >
              {/* Messages Container */}
              <Box
                sx={{
                  flex: 1,
                  minHeight: 0,
                  borderRadius: 2,
                  bgcolor: 'background.paper',
                  border: (theme) => `1px solid ${theme.palette.divider}`,
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
                  <Scrollbar
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      bottom: 0,
                      p: 3,
                      pb: 4,
                    }}
                  >
                    {messages.length === 0 ? (
                      <Box
                        sx={{
                          minHeight: '300px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexDirection: 'column',
                          gap: 2,
                        }}
                      >
                        <Box
                          sx={{
                            width: 80,
                            height: 80,
                            borderRadius: '50%',
                            bgcolor: 'action.hover',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            mb: 2,
                          }}
                        >
                          <Iconify
                            icon={'solar:chat-round-dots-bold' as any}
                            width={30}
                            sx={{ color: 'text.secondary' }}
                          />
                        </Box>
                        <Typography
                          variant='h6'
                          sx={{ fontWeight: 600, color: 'text.primary' }}
                        >
                          Start a Conversation
                        </Typography>
                        <Typography
                          variant='body2'
                          sx={{
                            color: 'text.secondary',
                            textAlign: 'center',
                            maxWidth: 400,
                            px: 2,
                          }}
                        >
                          Upload agricultural documents and ask questions about
                          farming practices, crop management, or soil health.
                        </Typography>
                      </Box>
                    ) : (
                      <>
                        {messages.map((msg) => (
                          <ChatMessage key={msg.id} message={msg} />
                        ))}
                        {isTyping && <TypingIndicator />}
                        <div ref={messagesEndRef} />
                      </>
                    )}
                  </Scrollbar>
                </Box>
              </Box>

              {/* Input - Fixed at bottom */}
              <Box sx={{ flexShrink: 0 }}>
                <ChatInput onSend={handleSend} loading={loading} />
              </Box>
            </Box>
          </Grid>

          {/* Document List */}
          <Grid size={{ xs: 12, md: 4 }}>
            <Box sx={{ height: '100%' }}>
              <DocumentList
                documents={documents}
                onUpload={() => setUploadOpen(true)}
                onDelete={handleDelete}
                deletingFile={deleting}
              />
            </Box>
          </Grid>
        </Grid>
      </Box>

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUpload={handleUpload}
      />
    </DashboardContent>
  );
}
