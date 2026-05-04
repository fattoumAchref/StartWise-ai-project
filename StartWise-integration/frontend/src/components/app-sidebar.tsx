"use client"

import * as React from "react"
import { useState, useEffect } from "react"
import { useTheme } from "next-themes"
import Image from "next/image"
import Link from "next/link"
import { useRouter } from "next/navigation"
import {
  Lamp,
  FileText,
  TrendingUp,
  Presentation,
} from "@mynaui/icons-react"
import { BarChart2, Scale, Building2, TriangleAlert } from "lucide-react"

import { NavMain } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
} from "@/components/ui/sidebar"
import { useApp } from "@/context/AppContext"

/**
 * Single-gate unlock — post-ideation tools become available once
 * startwise_summary exists OR the user sets startwise_unlocked=1.
 * Reach to Investors uses the same gate (marketing hub lives on /dashboard).
 */
function useJourneyStages() {
  const [stages, setStages] = useState({
    unlocked:      false,
    marketingDone: false,
  })

  const refresh = () => {
    const ideationDone  = !!localStorage.getItem('startwise_summary')
    const manualUnlock  = !!localStorage.getItem('startwise_unlocked')
    const unlocked      = ideationDone || manualUnlock
    const marketingDone = localStorage.getItem('startwise_workflow_status')
      ? (() => {
          try {
            const s = JSON.parse(localStorage.getItem('startwise_workflow_status')!)
            return s?.marketing_strategy === 'completed'
          } catch { return false }
        })()
      : false
    setStages({ unlocked, marketingDone })
  }

  useEffect(() => {
    refresh()
    window.addEventListener('storage', refresh)
    window.addEventListener('workflowUpdated', refresh)
    return () => {
      window.removeEventListener('storage', refresh)
      window.removeEventListener('workflowUpdated', refresh)
    }
  }, [])

  return stages
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const [mounted, setMounted] = useState(false)
  const { resolvedTheme } = useTheme()
  const router = useRouter()
  const app = useApp() as {
    analysisHistory: unknown
    loadAnalysis: (item: Record<string, unknown>) => void
  }
  const { analysisHistory, loadAnalysis } = app
  const stages = useJourneyStages()
  /** AppContext is .jsx — widen for .tsx */
  const marketingHistory = (analysisHistory ?? []) as Array<{
    id: string
    project: string
    date: string
    results?: Record<string, unknown>
  }>

  useEffect(() => { setMounted(true) }, [])

  const s = (locked: boolean, done = false): string =>
    done ? 'completed' : locked ? 'locked' : 'available'

  const getNavData = () => {
    const { unlocked, marketingDone } = stages
    const gtmStatus      = unlocked ? (marketingDone ? 'completed' : 'available') : 'locked'
    const investorsStatus = s(!unlocked)

    return [
      {
        title: "Ideation",
        url: "/dashboard/ideation",
        icon: Lamp,
        status: "completed",
        items: [],
      },
      {
        title: "Product Audit",
        url: "/dashboard/product-audit",
        icon: FileText,
        status: s(!unlocked),
        items: [],
      },
      {
        title: "Finance",
        url: "/dashboard/viability-assessment",
        icon: FileText,
        status: s(!unlocked),
        items: [],
      },
      {
        title: "Investment",
        url: "/dashboard/investment",
        icon: Building2,
        status: s(!unlocked),
        items: [],
      },
      {
        title: "Risk",
        url: "/dashboard/risk",
        icon: TriangleAlert,
        status: s(!unlocked),
        items: [],
      },
      {
        title: "LexWise",
        url: "/dashboard/lexwise",
        icon: Scale,
        status: s(!unlocked),
        items: [],
      },
      {
        title: "Go to Market",
        url: "/dashboard",
        icon: TrendingUp,
        status: gtmStatus,
        items: [],
      },
      {
        title: "Reach to Investors",
        url: "/dashboard#reach-investors",
        icon: Presentation,
        status: investorsStatus,
        items: [],
      },
    ]
  }

  const handleUnlockAll = () => {
    localStorage.setItem('startwise_unlocked', '1')
    window.dispatchEvent(new Event('workflowUpdated'))
  }

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="border-b border-sidebar-border/50">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild className="h-16 px-4 hover:bg-sidebar-accent/30 transition-colors duration-200">
              <Link href="/dashboard" className="flex items-center space-x-3">
                <div className="relative h-9 w-auto">
                  {!mounted ? (
                    // Placeholder during hydration
                    <div className="h-9 w-[138px] bg-sidebar-accent animate-pulse rounded" />
                  ) : (
                    <Image
                      src={resolvedTheme === 'dark' ? '/logo/dark.svg' : '/logo/white.svg'}
                      alt="Startwise"
                      width={138}
                      height={36}
                      className="h-9 w-[138px] object-contain"
                      priority
                    />
                  )}
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent className="px-2 py-4">
        {mounted && !stages.unlocked && (
          <div className="px-2 mb-3">
            <button
              onClick={handleUnlockAll}
              className="w-full rounded-lg py-2 px-3 text-xs font-semibold text-white transition-colors"
              style={{ background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', border: 'none', cursor: 'pointer' }}
            >
              Unlock all tools
            </button>
          </div>
        )}
        <NavMain items={getNavData()} />

        {/* Marketing Analysis History — only rendered client-side to avoid SSR/localStorage mismatch */}
        {mounted && marketingHistory.length > 0 && (
          <SidebarGroup className="mt-2">
            <SidebarGroupLabel className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground px-2">
              <BarChart2 className="h-3.5 w-3.5" />
              Marketing
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu className="gap-0.5">
                {marketingHistory.slice(0, 6).map((item, idx) => (
                  <SidebarMenuItem key={`${item.id}-${idx}`}>
                    <SidebarMenuButton
                      onClick={() => { loadAnalysis(item as Record<string, unknown>); router.push('/dashboard') }}
                      className="h-auto py-2 px-3 flex-col items-start hover:bg-sidebar-accent/50 cursor-pointer rounded-lg transition-colors"
                    >
                      <span className="text-xs font-medium truncate w-full text-sidebar-foreground leading-tight">
                        {item.project.slice(0, 45)}{item.project.length > 45 ? '…' : ''}
                      </span>
                      <div className="flex items-center gap-2 mt-0.5 w-full">
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(item.date).toLocaleDateString()}
                        </span>
                        {item.results && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 font-bold ml-auto">
                            ✓
                          </span>
                        )}
                      </div>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border/50 p-2">
        <NavUser user={{
          name: "Startwise User",
          email: "user@startwise.ai",
          avatar: "",
        }} />
      </SidebarFooter>
    </Sidebar>
  )
}
