"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { datasetsApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import { Download, Plus, X } from "lucide-react";

function ExportStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-gray-100 text-gray-700",
    running: "bg-amber-100 text-amber-700",
    done: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[status] ?? ""}`}>{status}</span>;
}

export default function DatasetsPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: datasets, isLoading } = useQuery({
    queryKey: ["datasets"],
    queryFn: datasetsApi.list,
  });

  const { data: exports } = useQuery({
    queryKey: ["exports", expandedId],
    queryFn: () => datasetsApi.exports(expandedId!),
    enabled: !!expandedId,
    refetchInterval: (q) =>
      q.state.data?.some((e) => e.status === "pending" || e.status === "running") ? 3000 : false,
  });

  const { mutate: create, isPending: creating } = useMutation({
    mutationFn: () => datasetsApi.create({ name, description: description || null, filter_config: {} }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["datasets"] });
      setShowForm(false);
      setName("");
      setDescription("");
    },
  });

  const { mutate: triggerExport } = useMutation({
    mutationFn: (id: string) => datasetsApi.triggerExport(id),
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: ["exports", id] }),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Datasets</h1>
        <Button onClick={() => setShowForm(!showForm)}>
          {showForm ? <X className="h-4 w-4 mr-1" /> : <Plus className="h-4 w-4 mr-1" />}
          {showForm ? "Cancel" : "New Dataset"}
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader><CardTitle className="text-base">Create Dataset</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. coding-q1-2026" />
            </div>
            <div className="space-y-2">
              <Label>Description <span className="text-muted-foreground font-normal">(optional)</span></Label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
            <Button onClick={() => create()} disabled={!name || creating}>
              {creating ? "Creating…" : "Create"}
            </Button>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
        </div>
      ) : (
        <div className="space-y-3">
          {datasets?.map((d) => (
            <Card key={d.id} className="cursor-pointer" onClick={() => setExpandedId(expandedId === d.id ? null : d.id)}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{d.name}</p>
                    {d.description && <p className="text-sm text-muted-foreground mt-0.5">{d.description}</p>}
                    <p className="text-xs text-muted-foreground mt-1">{formatDate(d.created_at)}</p>
                  </div>
                  <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); triggerExport(d.id); setExpandedId(d.id); }}>
                    <Download className="h-3.5 w-3.5 mr-1" />
                    Export JSONL
                  </Button>
                </div>

                {expandedId === d.id && exports && exports.length > 0 && (
                  <div className="mt-4 border-t border-border pt-4 space-y-2" onClick={(e) => e.stopPropagation()}>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Export History</p>
                    {exports.map((ex) => (
                      <div key={ex.id} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <ExportStatusBadge status={ex.status} />
                          <span className="text-muted-foreground">{ex.row_count != null ? `${ex.row_count} rows` : "—"}</span>
                          <span className="text-muted-foreground">{formatDate(ex.created_at)}</span>
                        </div>
                        {ex.download_url && (
                          <a href={ex.download_url} className="text-primary text-xs hover:underline" target="_blank" rel="noreferrer">
                            Download
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
          {datasets?.length === 0 && (
            <p className="text-center py-12 text-muted-foreground">No datasets yet. Create one to start exporting.</p>
          )}
        </div>
      )}
    </div>
  );
}
