import CreateNewFolderIcon from "@mui/icons-material/CreateNewFolder";
import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import GppGoodIcon from "@mui/icons-material/GppGood";
import {
  Box,
  Button,
  Card,
  CardActionArea,
  Stack,
  Typography,
} from "@mui/material";
import { useNavigate } from "react-router-dom";

/**
 * The engine's front door: one question, two answers.
 *
 * Cases are never listed here. A case is private to whoever knows its
 * reference, so the only way in is to type one.
 */
export default function StartPage() {
  const navigate = useNavigate();

  const choices = [
    {
      to: "/new",
      icon: <CreateNewFolderIcon sx={{ fontSize: 44 }} />,
      title: "Start a new case",
      body: "Give the case a reference you will remember. Then add evidence files and run the analysis.",
    },
    {
      to: "/open",
      icon: <FolderOpenIcon sx={{ fontSize: 44 }} />,
      title: "Open an existing case",
      body: "Enter the reference you used before to return to that case, its evidence, and its report.",
    },
  ];

  return (
    <Box sx={{ maxWidth: 880, mx: "auto", py: { xs: 2, md: 6 } }}>
      <Stack spacing={1.5} alignItems="center" sx={{ mb: 5, textAlign: "center" }}>
        <Box
          sx={{
            display: "grid",
            placeItems: "center",
            width: 76,
            height: 76,
            borderRadius: 3.5,
            bgcolor: "rgba(61,126,255,0.12)",
            color: "primary.main",
            mb: 0.5,
          }}
        >
          <GppGoodIcon sx={{ fontSize: 44 }} />
        </Box>
        <Typography variant="h4">Cybercrime Investigation Intelligence Engine</Typography>
        <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 560 }}>
          Digital evidence processing engine — acquire, analyse, and report on case evidence.
        </Typography>
        <Stack
          direction="row"
          spacing={1}
          flexWrap="wrap"
          useFlexGap
          justifyContent="center"
          sx={{ mt: 1 }}
        >
          {["OCR & Forensics", "Correlation", "Timeline", "Threat Intel", "Reports"].map(
            (label) => (
              <Typography
                key={label}
                variant="caption"
                sx={{
                  px: 1.25,
                  py: 0.4,
                  borderRadius: 999,
                  border: 1,
                  borderColor: "divider",
                  color: "text.secondary",
                  fontWeight: 600,
                }}
              >
                {label}
              </Typography>
            ),
          )}
        </Stack>
      </Stack>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5}>
        {choices.map((choice) => (
          <Card
            key={choice.to}
            sx={{
              flex: 1,
              "&:hover": { borderColor: "primary.main" },
            }}
          >
            <CardActionArea
              onClick={() => navigate(choice.to)}
              sx={{ height: "100%", p: 3.5 }}
            >
              <Stack spacing={1.5} alignItems="flex-start">
                <Box
                  sx={{
                    display: "grid",
                    placeItems: "center",
                    width: 64,
                    height: 64,
                    borderRadius: 3,
                    bgcolor: "rgba(61,126,255,0.10)",
                    color: "primary.main",
                  }}
                >
                  {choice.icon}
                </Box>
                <Typography variant="h6">{choice.title}</Typography>
                <Typography variant="body2" color="text.secondary">
                  {choice.body}
                </Typography>
              </Stack>
            </CardActionArea>
          </Card>
        ))}
      </Stack>

      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: "block", textAlign: "center", mt: 5 }}
      >
        Cases are reached by reference only — nothing on this machine lists them for you.
      </Typography>

      <Stack
        direction="row"
        spacing={2}
        justifyContent="center"
        alignItems="center"
        sx={{ mt: 4 }}
      >
        {/* Administrators can see and remove every case (password required). */}
        <Button
          size="small"
          variant="text"
          startIcon={<AdminPanelSettingsIcon />}
          onClick={() => navigate("/admin")}
        >
          Administrator
        </Button>
      </Stack>
    </Box>
  );
}
