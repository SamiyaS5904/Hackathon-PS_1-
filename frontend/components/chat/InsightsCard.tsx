"use client";

import { AlertTriangle, Lightbulb, MessageSquare } from "lucide-react";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui";
import { api } from "@/lib/api";
import { useChatPage } from "@/lib/chat-context";
import type { Insight } from "@/lib/types";

/** Proactive findings after generation; each one can be handed to the assistant as a question. */
export function InsightsCard({ revision }: { revision: string | number }) {
  const { ask } = useChatPage();
  const [items, setItems] = useState<Insight[] | null>(null);

  useEffect(() => {
    api.insights().then(setItems).catch(() => setItems(null));
  }, [revision]);

  if (!items || items.length === 0) return null;
  return (
    <Card className="mb-4 p-5">
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        <Lightbulb size={16} className="text-accent-text" aria-hidden /> Worth a look
      </h3>
      <ul className="mt-3 divide-y divide-border">
        {items.slice(0, 4).map((i) => (
          <li key={i.kind + i.title} className="flex flex-wrap items-start justify-between gap-3 py-2.5 text-sm">
            <span className="flex min-w-0 flex-1 gap-2">
              {i.severity === "warn" ? (
                <AlertTriangle size={16} className="mt-0.5 shrink-0 text-warn" aria-label="Needs attention" />
              ) : (
                <Lightbulb size={16} className="mt-0.5 shrink-0 text-muted" aria-label="Tip" />
              )}
              <span>
                {i.title}
                <span className="block text-xs text-muted">{i.detail}</span>
              </span>
            </span>
            <button
              type="button"
              onClick={() => ask(i.ask)}
              className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs text-accent-text hover:bg-surface-2"
            >
              <MessageSquare size={14} aria-hidden /> Ask the assistant
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
