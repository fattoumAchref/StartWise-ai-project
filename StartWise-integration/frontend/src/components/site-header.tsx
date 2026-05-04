'use client'

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { User, Settings, LogOut } from "lucide-react";
import DarkModeToggle from "./ui/DarkModeToggle";

export function SiteHeader() {
  const [hasRealData, setHasRealData] = useState<boolean | null>(null);

  useEffect(() => {
    try {
      const s = localStorage.getItem("startwise_summary");
      const b = localStorage.getItem("startwise_business_idea");
      setHasRealData(!!(s && b));
    } catch {
      setHasRealData(false);
    }
  }, []);

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-[[data-collapsible=icon]]/sidebar-wrapper:h-12 border-b">
      <div className="flex items-center gap-2 px-4 flex-1">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mx-2 data-[orientation=vertical]:h-4" />
        {/* Breadcrumb */}
        <nav className="flex items-center text-sm text-muted-foreground" aria-label="Breadcrumb">
          <ol className="flex items-center gap-1">
            <li>
              <a href="/dashboard" className="hover:underline font-medium text-foreground">Dashboard</a>
            </li>
            <li>
              <span className="mx-1">/</span>
            </li>
            <li className="text-muted-foreground">Documents</li>
          </ol>
        </nav>
        {hasRealData === null ? (
          <Badge variant="outline" className="ml-4 text-muted-foreground border-muted">
            …
          </Badge>
        ) : hasRealData ? (
          <Badge className="bg-green-100 text-green-800 border-green-200 ml-4">Live Data</Badge>
        ) : (
          <Badge variant="outline" className="bg-orange-100 text-orange-800 border-orange-200 ml-4">Demo Mode</Badge>
        )}
      </div>
      {/* Top Right Buttons */}
      <div className="flex items-center gap-2 px-4">
         <DarkModeToggle />
        <Button variant="ghost" size="sm">
          <User className="h-4 w-4 mr-2" />
          Profile
        </Button>
        <Button variant="ghost" size="sm">
          <Settings className="h-4 w-4 mr-2" />
          Settings
        </Button>
        <Button variant="ghost" size="sm">
          <LogOut className="h-4 w-4 mr-2" />
          Log Out
        </Button>
      </div>
    </header>
  );
}
