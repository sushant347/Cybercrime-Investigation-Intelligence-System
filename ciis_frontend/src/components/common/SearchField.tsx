import SearchIcon from "@mui/icons-material/Search";
import { InputAdornment, TextField, type TextFieldProps } from "@mui/material";
import { useEffect, useState } from "react";

/** Debounced search input used across every list view. */
export function SearchField({
  value,
  onSearch,
  delay = 350,
  ...rest
}: {
  value: string;
  onSearch: (value: string) => void;
  delay?: number;
} & Omit<TextFieldProps, "value" | "onChange">) {
  const [inner, setInner] = useState(value);

  useEffect(() => setInner(value), [value]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (inner !== value) onSearch(inner);
    }, delay);
    return () => window.clearTimeout(handle);
  }, [inner, value, delay, onSearch]);

  return (
    <TextField
      size="small"
      placeholder="Search…"
      value={inner}
      onChange={(e) => setInner(e.target.value)}
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" />
            </InputAdornment>
          ),
        },
      }}
      {...rest}
    />
  );
}
