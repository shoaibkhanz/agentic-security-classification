"use client";

import { useState } from "react";
import { ChevronDown, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CATEGORY_COLORS, CATEGORY_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { ClassificationRecord, SecurityCategory } from "@/lib/types";

interface HistoryTableProps {
  records: ClassificationRecord[];
  onDelete: (id: string) => void;
}

export function HistoryTable({ records, onDelete }: HistoryTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (records.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <p className="text-sm">No classifications yet.</p>
          <p className="text-xs mt-1">Run a classification to see it here.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40%]">Security</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Corrections</TableHead>
            <TableHead>Date</TableHead>
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {records.map((record) => {
            const isExpanded = expandedId === record.id;
            const category = record.result?.category as SecurityCategory;
            const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS.other;
            const confidence = record.result?.confidence;

            return (
              <>
                <TableRow
                  key={record.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() =>
                    setExpandedId(isExpanded ? null : record.id)
                  }
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <ChevronDown
                        className={cn(
                          "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                          isExpanded && "rotate-180"
                        )}
                      />
                      <span className="truncate max-w-[300px]">
                        {record.description.slice(0, 80)}
                        {record.description.length > 80 ? "..." : ""}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {category && (
                      <Badge
                        variant="secondary"
                        className={`${colors.bg} ${colors.text} text-[10px]`}
                      >
                        {CATEGORY_LABELS[category] || category}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {confidence != null && (
                      <span className="font-mono text-sm">
                        {Math.round(confidence * 100)}%
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {record.corrections.length > 0 && (
                      <Badge variant="outline" className="text-[10px]">
                        {record.corrections.length}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(record.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(record.id);
                      }}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>

                {isExpanded && (
                  <TableRow key={`${record.id}-detail`}>
                    <TableCell colSpan={6} className="bg-muted/20 p-4">
                      <div className="space-y-3 text-sm">
                        {/* Summary */}
                        {record.result?.summary && (
                          <div>
                            <span className="font-medium">Summary: </span>
                            <span className="text-muted-foreground">
                              {record.result.summary}
                            </span>
                          </div>
                        )}

                        {/* Questions asked */}
                        {record.result?.questions_asked != null && (
                          <div className="text-xs text-muted-foreground">
                            Questions asked: {record.result.questions_asked}
                          </div>
                        )}

                        {/* Corrections */}
                        {record.corrections.length > 0 && (
                          <div className="space-y-2">
                            <span className="text-xs font-medium">
                              Corrections:
                            </span>
                            {record.corrections.map((c, i) => (
                              <div
                                key={i}
                                className="rounded border bg-background p-2 text-xs"
                              >
                                <p>{c.feedback}</p>
                                {c.correct_category && (
                                  <p className="mt-1 text-muted-foreground">
                                    Suggested: {c.correct_category}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </>
            );
          })}
        </TableBody>
      </Table>
    </Card>
  );
}
