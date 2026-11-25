import { Typography } from "@material-tailwind/react";
import {
  WrenchScrewdriverIcon,
} from "@heroicons/react/24/solid";

/**
 * Reusable placeholder for sections that are under development.
 * Props:
 *   title    - the page name, e.g. "Dining Manager"
 *   section  - the parent section, e.g. "Commerce & Service Managers"
 *   taskId   - the sprint task ID, e.g. "AR-1.10"
 *   assignee - who owns this task, e.g. "Anusha Ronda"
 */
export default function ComingSoon({
  title = "This Page",
  section = "",
  taskId = "",
  assignee = "",
}) {
  return (
    <main className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8">
      <div className="rounded-full bg-blue-50 p-5">
        <WrenchScrewdriverIcon className="h-12 w-12 text-blue-500" />
      </div>

      <Typography variant="h4" color="blue-gray" className="text-center">
        {title}
      </Typography>

      <Typography
        variant="paragraph"
        color="blue-gray"
        className="max-w-md text-center opacity-70"
      >
        This screen is under active development as part of{" "}
        <strong>Phase 1 Sprint</strong>.
        {section && (
          <>
            {" "}
            It belongs to the <strong>{section}</strong> section.
          </>
        )}
      </Typography>

      {(taskId || assignee) && (
        <div className="mt-2 flex items-center gap-3 rounded-lg border border-blue-gray-100 bg-white px-5 py-3 shadow-sm">
          {taskId && (
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
              {taskId}
            </span>
          )}
          {assignee && (
            <Typography variant="small" color="blue-gray">
              Assigned to <strong>{assignee}</strong>
            </Typography>
          )}
        </div>
      )}

      <Typography variant="small" color="blue-gray" className="mt-4 opacity-50">
        Check back after the next sprint update.
      </Typography>
    </main>
  );
}
