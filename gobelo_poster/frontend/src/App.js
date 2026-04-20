import React, { useState, useEffect } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Container, Typography, Box, Card, CardContent, Button, Select, MenuItem, FormControl, InputLabel } from '@mui/material';
import { Language, Refresh } from '@mui/icons-material';

// Design tokens
const theme = createTheme({
  palette: {
    primary: {
      main: '#c8711a',
    },
    secondary: {
      main: '#2c5f6e',
    },
    background: {
      default: '#fdf6e8',
      paper: '#f5ede0',
    },
    text: {
      primary: '#1a1108',
      secondary: '#6b5240',
    },
  },
  typography: {
    fontFamily: "'DM Sans', system-ui, sans-serif",
    h1: {
      fontFamily: "'DM Serif Display', Georgia, serif",
      fontSize: '2.5rem',
      fontWeight: 400,
    },
    h2: {
      fontFamily: "'DM Serif Display', Georgia, serif",
      fontSize: '2rem',
      fontWeight: 400,
    },
  },
});

// Language data
const LANGS = {
  chitonga:  { name: "ChiTonga",  iso: "toi", guthrie: "M.64", region: "Southern Province", color: "#2c5f6e" },
  chibemba:  { name: "Chibemba",  iso: "bem", guthrie: "M.42", region: "Copperbelt / Luapula", color: "#a04030" },
  chinyanja: { name: "ChiNyanja", iso: "nya", guthrie: "N.31", region: "Eastern Province / Lusaka", color: "#3a6b3e" },
  silozi:    { name: "SiLozi",    iso: "loz", guthrie: "K.21", region: "Western Province", color: "#c8711a" },
  cikaonde:  { name: "ciKaonde",  iso: "kqn", guthrie: "L.41", region: "North-Western Province", color: "#8b6f4e" },
  ciluvale:  { name: "ciLuvale",  iso: "lue", guthrie: "K.14", region: "North-Western Province", color: "#5a7a3a" },
  cilunda:   { name: "ciLunda",   iso: "lun", guthrie: "L.52", region: "North-Western Province", color: "#6a4a7a" },
};

function App() {
  const [wordOfDay, setWordOfDay] = useState(null);
  const [selectedLang, setSelectedLang] = useState('chitonga');
  const [loading, setLoading] = useState(false);

  const fetchWordOfDay = async (lang) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/wotd?lang=${lang}`);
      const data = await response.json();
      setWordOfDay(data);
    } catch (error) {
      console.error('Error fetching word of the day:', error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchWordOfDay(selectedLang);
  }, [selectedLang]);

  const handleLanguageChange = (event) => {
    setSelectedLang(event.target.value);
  };

  const handleRefresh = () => {
    fetchWordOfDay(selectedLang);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="md" sx={{ py: 4 }}>
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Typography variant="h1" component="h1" gutterBottom>
            Gobelo Platform
          </Typography>
          <Typography variant="h2" component="h2" color="text.secondary">
            Bantu Language Learning
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <FormControl sx={{ minWidth: 200, mr: 2 }}>
            <InputLabel>Select Language</InputLabel>
            <Select
              value={selectedLang}
              label="Select Language"
              onChange={handleLanguageChange}
              startAdornment={<Language sx={{ mr: 1 }} />}
            >
              {Object.entries(LANGS).map(([key, lang]) => (
                <MenuItem key={key} value={key}>
                  {lang.name} ({lang.iso})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={handleRefresh}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>

        {wordOfDay && (
          <Card sx={{ maxWidth: 600, mx: 'auto', bgcolor: 'background.paper' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h3" component="h2" gutterBottom sx={{ fontFamily: "'DM Serif Display', serif" }}>
                Word of the Day
              </Typography>
              <Typography variant="h4" component="h3" sx={{ color: LANGS[selectedLang]?.color, mb: 2 }}>
                {wordOfDay.word}
              </Typography>
              <Typography variant="body1" sx={{ mb: 2, fontSize: '1.1rem' }}>
                {wordOfDay.gloss}
              </Typography>
              {wordOfDay.example && (
                <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary' }}>
                  Example: {wordOfDay.example}
                </Typography>
              )}
              <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {wordOfDay.pos && (
                  <Typography variant="caption" sx={{ bgcolor: 'primary.main', color: 'white', px: 1, py: 0.5, borderRadius: 1 }}>
                    {wordOfDay.pos}
                  </Typography>
                )}
                {wordOfDay.nc && (
                  <Typography variant="caption" sx={{ bgcolor: 'secondary.main', color: 'white', px: 1, py: 0.5, borderRadius: 1 }}>
                    {wordOfDay.nc}
                  </Typography>
                )}
                {wordOfDay.prefix && (
                  <Typography variant="caption" sx={{ bgcolor: 'background.default', color: 'text.primary', px: 1, py: 0.5, borderRadius: 1, border: 1, borderColor: 'divider' }}>
                    prefix: {wordOfDay.prefix}
                  </Typography>
                )}
              </Box>
            </CardContent>
          </Card>
        )}

        {loading && (
          <Box sx={{ textAlign: 'center', mt: 4 }}>
            <Typography>Loading...</Typography>
          </Box>
        )}
      </Container>
    </ThemeProvider>
  );
}

export default App;