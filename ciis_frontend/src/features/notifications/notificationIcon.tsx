import CampaignIcon from "@mui/icons-material/Campaign";
import ErrorIcon from "@mui/icons-material/Error";
import GppMaybeIcon from "@mui/icons-material/GppMaybe";
import PriorityHighIcon from "@mui/icons-material/PriorityHigh";
import SummarizeIcon from "@mui/icons-material/Summarize";
import TaskAltIcon from "@mui/icons-material/TaskAlt";
import type { ReactElement } from "react";

import { BRAND } from "@/theme/theme";
import type { NotificationType } from "@/types";

export function notificationIcon(type: NotificationType): ReactElement {
  switch (type) {
    case "processing_complete":
      return <TaskAltIcon sx={{ color: BRAND.low }} />;
    case "high_priority":
      return <PriorityHighIcon sx={{ color: BRAND.critical }} />;
    case "forgery_warning":
      return <GppMaybeIcon sx={{ color: BRAND.high }} />;
    case "threat_detected":
      return <CampaignIcon sx={{ color: BRAND.high }} />;
    case "report_generated":
      return <SummarizeIcon sx={{ color: BRAND.primary }} />;
    case "system_error":
      return <ErrorIcon sx={{ color: BRAND.critical }} />;
  }
}
