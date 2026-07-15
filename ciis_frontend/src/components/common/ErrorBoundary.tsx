import { Button } from "@mui/material";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { EmptyState } from "./EmptyState";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI error boundary caught:", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <EmptyState
          title="Something went wrong in this view"
          description={this.state.error.message}
          action={
            <Button variant="contained" onClick={() => this.setState({ error: null })}>
              Reset view
            </Button>
          }
        />
      );
    }
    return this.props.children;
  }
}
