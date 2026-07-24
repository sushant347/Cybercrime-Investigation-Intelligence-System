import CreateNewFolderIcon from "@mui/icons-material/CreateNewFolder";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import GppGoodIcon from "@mui/icons-material/GppGood";
import { Box, Card, CardActionArea, Stack, Typography } from "@mui/material";
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
      <Stack spacing={1} alignItems="center" sx={{ mb: 5, textAlign: "center" }}>
        <GppGoodIcon color="primary" sx={{ fontSize: 52 }} />
        <Typography variant="h4">Cybercrime Investigation Intelligence System</Typography>
        <Typography variant="body1" color="text.secondary">
          Digital evidence processing engine — acquire, analyse, and report on case evidence.
        </Typography>
      </Stack>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2.5}>
        {choices.map((choice) => (
          <Card key={choice.to} sx={{ flex: 1 }}>
            <CardActionArea
              onClick={() => navigate(choice.to)}
              sx={{ height: "100%", p: 3.5 }}
            >
              <Stack spacing={1.5} alignItems="flex-start">
                <Box sx={{ color: "primary.main" }}>{choice.icon}</Box>
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
    </Box>
  );
}
