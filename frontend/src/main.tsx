import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Edit3, Plus, RefreshCcw, Save, Search, Trash2, X } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type MessageType = "customer_msg" | "support_msg" | "internal_memo";

type RmaThread = {
  id: string;
  rma_number: string;
  title: string | null;
  customer_name: string | null;
  created_at: string;
  updated_at: string;
  latest_message_preview: string | null;
};

type Message = {
  id: string;
  rma_thread_id: string;
  type: MessageType;
  content: string;
  attachment_url: string | null;
  attachment_filename: string | null;
  attachment_mime_type: string | null;
  attachment_size: number | null;
  created_at: string;
};

type BoardThread = RmaThread & {
  messages: Message[];
};

type BoardResponse = {
  items: BoardThread[];
  total: number;
  limit: number;
  offset: number;
};

const typeLabel: Record<MessageType, string> = {
  customer_msg: "お客様",
  support_msg: "サポート",
  internal_memo: "社内メモ",
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    headers: isFormData
      ? options?.headers
      : {
          "Content-Type": "application/json",
          ...options?.headers,
        },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "API request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function App() {
  const [threads, setThreads] = useState<RmaThread[]>([]);
  const [messagesByRma, setMessagesByRma] = useState<Record<string, Message[]>>({});
  const [draftByRma, setDraftByRma] = useState<Record<string, string>>({});
  const [attachmentByRma, setAttachmentByRma] = useState<Record<string, File | null>>({});
  const [rmaSearch, setRmaSearch] = useState("");
  const [keywordSearch, setKeywordSearch] = useState("");
  const [exact, setExact] = useState(false);
  const [newRma, setNewRma] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newCustomerName, setNewCustomerName] = useState("");
  const [editingThreadRma, setEditingThreadRma] = useState<string | null>(null);
  const [threadTitleDraft, setThreadTitleDraft] = useState("");
  const [threadCustomerDraft, setThreadCustomerDraft] = useState("");
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [messageContentDraft, setMessageContentDraft] = useState("");
  const [messageTypeDraft, setMessageTypeDraft] = useState<MessageType>("internal_memo");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const totalMessages = useMemo(
    () => Object.values(messagesByRma).reduce((sum, messages) => sum + messages.length, 0),
    [messagesByRma],
  );

  async function loadBoard() {
    setLoading(true);
    setNotice("");

    try {
      const params = new URLSearchParams();
      if (rmaSearch.trim()) params.set("rma", rmaSearch.trim());
      if (keywordSearch.trim()) params.set("keyword", keywordSearch.trim());
      if (exact) params.set("rma_match", "exact");

      const data = await request<BoardResponse>(`/board?${params}`);
      setThreads(data.items);
      setMessagesByRma(
        Object.fromEntries(
          data.items.map((thread) => [thread.rma_number, thread.messages] as const),
        ),
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to load board.");
    } finally {
      setLoading(false);
    }
  }

  async function createThread() {
    const rma = newRma.trim();
    if (!rma) return;

    setNotice("");
    try {
      const thread = await request<RmaThread>("/rma-threads", {
        method: "POST",
        body: JSON.stringify({
          rma_number: rma,
          title: newTitle.trim() || null,
          customer_name: newCustomerName.trim() || null,
        }),
      });
      setNewRma("");
      setNewTitle("");
      setNewCustomerName("");
      setRmaSearch(rma);
      setExact(true);
      setThreads((current) => [thread, ...current.filter((item) => item.id !== thread.id)]);
      setMessagesByRma((current) => ({ ...current, [thread.rma_number]: [] }));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to create thread.");
    }
  }

  function startThreadEdit(thread: RmaThread) {
    setEditingThreadRma(thread.rma_number);
    setThreadTitleDraft(thread.title ?? "");
    setThreadCustomerDraft(thread.customer_name ?? "");
  }

  async function saveThread(thread: RmaThread) {
    setNotice("");
    try {
      const updated = await request<RmaThread>(
        `/rma-threads/${encodeURIComponent(thread.rma_number)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title: threadTitleDraft.trim() || null,
            customer_name: threadCustomerDraft.trim() || null,
          }),
        },
      );
      setThreads((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setEditingThreadRma(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to update thread.");
    }
  }

  async function addMessage(rmaNumber: string, type: MessageType) {
    const content = draftByRma[rmaNumber]?.trim();
    const attachment = attachmentByRma[rmaNumber];
    if (!content && !attachment) return;

    setNotice("");
    try {
      const body = new FormData();
      body.set("type", type);
      body.set("content", content);
      if (attachment) body.set("attachment", attachment);

      await request<Message>(`/rma-threads/${encodeURIComponent(rmaNumber)}/messages`, {
        method: "POST",
        body,
      });
      setDraftByRma((current) => ({ ...current, [rmaNumber]: "" }));
      setAttachmentByRma((current) => ({ ...current, [rmaNumber]: null }));
      await loadBoard();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to add log.");
    }
  }

  function startMessageEdit(message: Message) {
    setEditingMessageId(message.id);
    setMessageContentDraft(message.content);
    setMessageTypeDraft(message.type);
  }

  async function saveMessage(rmaNumber: string, message: Message) {
    setNotice("");
    try {
      const updated = await request<Message>(`/messages/${encodeURIComponent(message.id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          type: messageTypeDraft,
          content: messageContentDraft.trim(),
        }),
      });
      setMessagesByRma((current) => ({
        ...current,
        [rmaNumber]: (current[rmaNumber] ?? []).map((item) =>
          item.id === updated.id ? updated : item,
        ),
      }));
      setEditingMessageId(null);
      await loadBoard();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to update log.");
    }
  }

  async function deleteThread(rmaNumber: string) {
    const ok = window.confirm(
      `Delete ${rmaNumber}? This will remove all logs and attachments in this thread.`,
    );
    if (!ok) return;

    setNotice("");
    try {
      await request<void>(`/rma-threads/${encodeURIComponent(rmaNumber)}`, {
        method: "DELETE",
      });
      setThreads((current) => current.filter((thread) => thread.rma_number !== rmaNumber));
      setMessagesByRma((current) => {
        const next = { ...current };
        delete next[rmaNumber];
        return next;
      });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to delete thread.");
    }
  }

  async function deleteMessage(rmaNumber: string, messageId: string) {
    const ok = window.confirm("Delete this log?");
    if (!ok) return;

    setNotice("");
    try {
      await request<void>(`/messages/${encodeURIComponent(messageId)}`, {
        method: "DELETE",
      });
      setMessagesByRma((current) => ({
        ...current,
        [rmaNumber]: (current[rmaNumber] ?? []).filter((message) => message.id !== messageId),
      }));
      await loadBoard();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to delete log.");
    }
  }

  useEffect(() => {
    void loadBoard();
  }, []);

  return (
    <main className="board">
      <header className="topbar">
        <div>
          <p>GPU SUPPORT LOG</p>
          <h1>RMA Board</h1>
        </div>
        <button className="ghostButton" onClick={loadBoard} title="Reload" aria-label="Reload">
          <RefreshCcw size={18} />
        </button>
      </header>

      <section className="tools" aria-label="Board controls">
        <div className="searchLine">
          <label>
            <span>RMA</span>
            <input
              value={rmaSearch}
              onChange={(event) => setRmaSearch(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && loadBoard()}
              placeholder="RMA-0001"
            />
          </label>
          <label>
            <span>Keyword</span>
            <input
              value={keywordSearch}
              onChange={(event) => setKeywordSearch(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && loadBoard()}
              placeholder="error, artifact, fan..."
            />
          </label>
          <label className="exactBox">
            <input
              type="checkbox"
              checked={exact}
              onChange={(event) => setExact(event.target.checked)}
            />
            exact
          </label>
          <button className="solidButton" onClick={loadBoard}>
            <Search size={16} />
            Search
          </button>
        </div>

        <div className="newLine">
          <input
            value={newRma}
            onChange={(event) => setNewRma(event.target.value)}
            placeholder="New RMA number"
          />
          <input
            value={newTitle}
            onChange={(event) => setNewTitle(event.target.value)}
            placeholder="Thread title"
          />
          <input
            value={newCustomerName}
            onChange={(event) => setNewCustomerName(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && createThread()}
            placeholder="Customer name"
          />
          <button className="solidButton" onClick={createThread}>
            <Plus size={16} />
            New thread
          </button>
        </div>
      </section>

      <div className="metaLine">
        <span>{threads.length} threads</span>
        <span>{totalMessages} logs</span>
        {loading && <span>loading...</span>}
      </div>

      {notice && <p className="notice">{notice}</p>}

      <section className="threadStack" aria-label="RMA threads">
        {threads.length === 0 ? (
          <div className="emptyBoard">No RMA threads yet.</div>
        ) : (
          threads.map((thread) => {
            const messages = messagesByRma[thread.rma_number] ?? [];
            const draft = draftByRma[thread.rma_number] ?? "";
            const attachment = attachmentByRma[thread.rma_number];
            const isThreadEditing = editingThreadRma === thread.rma_number;

            return (
              <article className="thread" key={thread.id}>
                <header className="threadHeader">
                  {isThreadEditing ? (
                    <div className="threadEditGrid">
                      <input
                        value={threadTitleDraft}
                        onChange={(event) => setThreadTitleDraft(event.target.value)}
                        placeholder="Thread title"
                      />
                      <input
                        value={threadCustomerDraft}
                        onChange={(event) => setThreadCustomerDraft(event.target.value)}
                        placeholder="Customer name"
                      />
                    </div>
                  ) : (
                    <div className="threadTitleBlock">
                      <h2>{thread.title || thread.rma_number}</h2>
                      <p>
                        <span>RMA: {thread.rma_number}</span>
                        <span>Customer: {thread.customer_name || "-"}</span>
                      </p>
                    </div>
                  )}

                  <div className="headerActions">
                    <time>{formatDate(thread.updated_at)}</time>
                    {isThreadEditing ? (
                      <>
                        <button
                          className="iconAction"
                          onClick={() => saveThread(thread)}
                          title="Save thread"
                          aria-label="Save thread"
                        >
                          <Save size={15} />
                        </button>
                        <button
                          className="iconAction"
                          onClick={() => setEditingThreadRma(null)}
                          title="Cancel"
                          aria-label="Cancel"
                        >
                          <X size={15} />
                        </button>
                      </>
                    ) : (
                      <button
                        className="iconAction"
                        onClick={() => startThreadEdit(thread)}
                        title="Edit thread"
                        aria-label="Edit thread"
                      >
                        <Edit3 size={15} />
                      </button>
                    )}
                    <button
                      className="dangerButton"
                      onClick={() => deleteThread(thread.rma_number)}
                      title="Delete thread"
                      aria-label="Delete thread"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </header>

                <div className="posts">
                  {messages.length === 0 ? (
                    <p className="noPosts">No logs. Add the first one below.</p>
                  ) : (
                    messages.map((message, index) => {
                      const isMessageEditing = editingMessageId === message.id;

                      return (
                        <section className={`postRow ${message.type}`} key={message.id}>
                          <div className="avatar">{typeLabel[message.type]}</div>
                          <article className="bubble">
                            <div className="postMeta">
                              <strong>#{index + 1}</strong>
                              <span>
                                <time>{formatDate(message.created_at)}</time>
                                {isMessageEditing ? (
                                  <>
                                    <button
                                      className="messageAction"
                                      onClick={() => saveMessage(thread.rma_number, message)}
                                      title="Save log"
                                      aria-label="Save log"
                                    >
                                      <Save size={14} />
                                    </button>
                                    <button
                                      className="messageAction"
                                      onClick={() => setEditingMessageId(null)}
                                      title="Cancel"
                                      aria-label="Cancel"
                                    >
                                      <X size={14} />
                                    </button>
                                  </>
                                ) : (
                                  <button
                                    className="messageAction"
                                    onClick={() => startMessageEdit(message)}
                                    title="Edit log"
                                    aria-label="Edit log"
                                  >
                                    <Edit3 size={14} />
                                  </button>
                                )}
                                <button
                                  className="messageDelete"
                                  onClick={() => deleteMessage(thread.rma_number, message.id)}
                                  title="Delete log"
                                  aria-label="Delete log"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </span>
                            </div>

                            {isMessageEditing ? (
                              <div className="messageEditBox">
                                <select
                                  value={messageTypeDraft}
                                  onChange={(event) =>
                                    setMessageTypeDraft(event.target.value as MessageType)
                                  }
                                >
                                  <option value="customer_msg">お客様</option>
                                  <option value="support_msg">サポート</option>
                                  <option value="internal_memo">社内メモ</option>
                                </select>
                                <textarea
                                  value={messageContentDraft}
                                  onChange={(event) => setMessageContentDraft(event.target.value)}
                                  rows={3}
                                />
                              </div>
                            ) : (
                              <>
                                {message.content && <p>{message.content}</p>}
                                {message.attachment_url && <AttachmentPreview message={message} />}
                              </>
                            )}
                          </article>
                        </section>
                      );
                    })
                  )}
                </div>

                <footer className="replyBox">
                  <textarea
                    value={draft}
                    onChange={(event) =>
                      setDraftByRma((current) => ({
                        ...current,
                        [thread.rma_number]: event.target.value,
                      }))
                    }
                    placeholder="Paste or type the log here"
                    rows={3}
                  />
                  <div className="attachLine">
                    <label className="filePicker">
                      <span>画像/動画を添付</span>
                      <input
                        type="file"
                        accept="image/*,video/*"
                        onChange={(event) =>
                          setAttachmentByRma((current) => ({
                            ...current,
                            [thread.rma_number]: event.target.files?.[0] ?? null,
                          }))
                        }
                      />
                    </label>
                    {attachment && <span className="fileName">{attachment.name}</span>}
                  </div>
                  <div className="replyButtons">
                    <button onClick={() => addMessage(thread.rma_number, "customer_msg")}>
                      お客様として追加
                    </button>
                    <button onClick={() => addMessage(thread.rma_number, "support_msg")}>
                      サポートとして追加
                    </button>
                    <button onClick={() => addMessage(thread.rma_number, "internal_memo")}>
                      MEMO
                    </button>
                  </div>
                </footer>
              </article>
            );
          })
        )}
      </section>
    </main>
  );
}

function AttachmentPreview({ message }: { message: Message }) {
  const src = `${API_BASE}${message.attachment_url}`;
  const filename = message.attachment_filename ?? "attachment";

  if (message.attachment_mime_type?.startsWith("image/")) {
    return <img className="attachmentPreview" src={src} alt={filename} />;
  }

  if (message.attachment_mime_type?.startsWith("video/")) {
    return (
      <video className="attachmentPreview" controls>
        <source src={src} type={message.attachment_mime_type} />
      </video>
    );
  }

  return (
    <a className="attachmentLink" href={src} target="_blank" rel="noreferrer">
      {filename}
    </a>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
