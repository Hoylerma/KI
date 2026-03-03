import {
  ThreadPrimitive,
  MessagePrimitive,
  ComposerPrimitive,
  MessagePartPrimitive,
} from '@assistant-ui/react';
import { MarkdownTextPrimitive } from '@assistant-ui/react-markdown';
import { ArrowUp, Square, Bot } from 'lucide-react';

function UserTextPart() {
  return (
    <MessagePartPrimitive.Text
      component="p"
      className="whitespace-pre-wrap break-words"
    />
  );
}

function AssistantTextPart() {
  return <MarkdownTextPrimitive className="prose prose-sm max-w-none" />;
}

function AssistantEmptyPart() {
  return (
    <MessagePartPrimitive.InProgress>
      <span className="inline-flex gap-1 py-1">
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
      </span>
    </MessagePartPrimitive.InProgress>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end px-4 pb-4 w-full max-w-3xl mx-auto">
      <div className="max-w-[70%] bg-[#2f2f2f] text-white rounded-3xl px-4 py-3 text-sm">
        <MessagePrimitive.Parts
          components={{
            Text: UserTextPart,
          }}
        />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-start gap-3 px-4 pb-4 w-full max-w-3xl mx-auto">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#171717] flex items-center justify-center mt-1">
        <Bot size={16} className="text-[#ffe000]" />
      </div>
      <div className="flex-1 min-w-0 text-sm text-gray-800">
        <MessagePrimitive.Parts
          components={{
            Text: AssistantTextPart,
            Empty: AssistantEmptyPart,
          }}
        />
      </div>
    </MessagePrimitive.Root>
  );
}

export default function Thread() {
  return (
    <ThreadPrimitive.Root className="flex flex-col h-full bg-white">
      <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto py-6">
        <ThreadPrimitive.Empty>
          <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-3">
            <div className="w-16 h-16 rounded-full bg-[#171717] flex items-center justify-center">
              <Bot size={32} className="text-[#ffe000]" />
            </div>
            <h1 className="text-2xl font-semibold text-gray-800">Bw-I Chatbot</h1>
            <p className="text-gray-500 text-sm">Intelligente Hilfe für Bundeswehr-Informationen</p>
          </div>
        </ThreadPrimitive.Empty>
        <ThreadPrimitive.Messages
          components={{
            UserMessage,
            AssistantMessage,
          }}
        />
      </ThreadPrimitive.Viewport>

      <div className="px-4 pb-4 pt-2 bg-white flex-shrink-0">
        <ComposerPrimitive.Root className="flex items-end max-w-3xl mx-auto bg-gray-100 rounded-2xl px-4 py-3 gap-3 shadow-sm">
          <ComposerPrimitive.Input
            className="flex-1 bg-transparent text-sm resize-none focus:outline-none max-h-48 leading-6 placeholder:text-gray-400"
            placeholder="Schreibe eine Nachricht..."
            rows={1}
          />
          <ComposerPrimitive.Send className="flex-shrink-0 w-8 h-8 bg-black text-white rounded-full flex items-center justify-center hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors">
            <ArrowUp size={16} />
          </ComposerPrimitive.Send>
          <ComposerPrimitive.Cancel className="hidden flex-shrink-0 w-8 h-8 bg-gray-300 text-black rounded-full items-center justify-center hover:bg-gray-400 cursor-pointer transition-colors [&:not([disabled])]:flex">
            <Square size={14} />
          </ComposerPrimitive.Cancel>
        </ComposerPrimitive.Root>
      </div>
    </ThreadPrimitive.Root>
  );
}
