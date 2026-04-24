"use client"

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

interface DeleteCandidateDialogProps {
  /** The candidate pending deletion, or null when the dialog is closed. */
  candidate: { id: string; name: string } | null
  /** True while the delete request is in-flight. */
  deleting: boolean
  /** Called when the user confirms deletion. */
  onConfirm: () => void
  /** Called when the user cancels or closes the dialog. */
  onCancel: () => void
}

export function DeleteCandidateDialog({
  candidate,
  deleting,
  onConfirm,
  onCancel,
}: DeleteCandidateDialogProps) {
  return (
    <AlertDialog
      open={!!candidate}
      onOpenChange={(open) => {
        if (!open) onCancel()
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete candidate?</AlertDialogTitle>
          <AlertDialogDescription>
            {candidate
              ? `This will permanently remove ${candidate.name} from the system.`
              : "This action cannot be undone."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-destructive text-white hover:bg-destructive/90"
          >
            {deleting ? "Deleting..." : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
