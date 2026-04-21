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
  Grid,
  Target,
  TrendingUp,
  Presentation,
  ChartLine,
} from "@mynaui/icons-react"
import { BarChart2 } from "lucide-react"

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
import { getWorkflowStatus, WorkflowStatus } from "@/services/agents"
import { useApp } from "@/context/AppContext"

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const [mounted, setMounted] = useState(false)
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | null>(null)
  const { resolvedTheme } = useTheme()
  const router = useRouter()
  const { analysisHistory, loadAnalysis } = useApp()

  useEffect(() => {
    setMounted(true)
    // Load workflow status
    loadWorkflowStatus()
    
    // Listen for storage changes to update sidebar
    const handleStorageChange = () => {
      loadWorkflowStatus()
    }
    
    window.addEventListener('storage', handleStorageChange)
    // Also listen for custom events when localStorage is updated in the same tab
    window.addEventListener('workflowUpdated', handleStorageChange)
    
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('workflowUpdated', handleStorageChange)
    }
  }, [])

  const loadWorkflowStatus = async () => {
    try {
      const status = await getWorkflowStatus()
      console.log('Sidebar workflow status:', status)
      
      // Check actual data existence to override status if needed
      if (typeof window !== 'undefined') {
        const financialData = localStorage.getItem('startwise_financial_data');
        const marketData = localStorage.getItem('startwise_market_data');
        const swotData = localStorage.getItem('startwise_swot_data');
        const bmcData = localStorage.getItem('startwise_bmc_data');
        const brandIdentityData = localStorage.getItem('startwise_brand_identity_data');
        
        // Update status based on actual data
        const dataBasedStatus = { ...status };
        if (financialData && marketData) {
          dataBasedStatus.viability_assessment = 'completed';
          // After viability assessment is completed, unlock SWOT
          if (dataBasedStatus.swot_analysis === 'locked') {
            dataBasedStatus.swot_analysis = 'available';
          }
        }
        if (swotData) {
          dataBasedStatus.swot_analysis = 'completed';
          // After SWOT is completed, unlock BMC
          if (dataBasedStatus.bmc === 'locked') {
            dataBasedStatus.bmc = 'available';
          }
        }
        if (bmcData) {
          dataBasedStatus.bmc = 'completed';
          // After BMC is completed, unlock Brand Identity
          if (!brandIdentityData) {
            dataBasedStatus.brand_identity = 'available';
          }
        }
        if (brandIdentityData) {
          dataBasedStatus.brand_identity = 'completed';
          // After Brand Identity is completed, unlock Marketing Strategy
          if (dataBasedStatus.marketing_strategy === 'locked') {
            dataBasedStatus.marketing_strategy = 'available';
          }
        }
        
        setWorkflowStatus(dataBasedStatus);
      } else {
        setWorkflowStatus(status);
      }
    } catch (error) {
      console.error('Failed to load workflow status:', error)
      // Set a default fallback status
      setWorkflowStatus({
        ideation: 'completed',
        viability_assessment: 'locked',
        swot_analysis: 'locked', 
        bmc: 'locked',
        brand_identity: 'locked',
        marketing_strategy: 'locked',
        pitch_deck: 'locked'
      })
    }
  }

  // Create navigation data with dynamic status
  const getNavData = () => {
    return [
      {
        title: "Ideation",
        url: "/dashboard/ideation",
        icon: Lamp,
        status: "completed", // Always completed after onboarding
        items: [],
      },
      {
        title: "Product Audit",
        url: "/dashboard/product-audit",
        icon: FileText,
        status: "available",
        items: [],
      },
      {
        title: "Viability Assessment",
        url: "/dashboard/viability-assessment",
        icon: FileText,
        status: workflowStatus?.viability_assessment || "locked",
        progress: 0,
        items: [],
      },
      {
        title: "SWOT Analysis",
        url: "/dashboard/swot-analysis",
        icon: ChartLine,
        status: workflowStatus?.swot_analysis || "locked",
        items: [],
      },
      {
        title: "Business Model Canvas",
        url: "/dashboard/bmc",
        icon: Grid,
        status: workflowStatus?.bmc || "locked",
        items: [],
      },
      {
        title: "Brand Identity",
        url: "/dashboard/brand-identity",
        icon: Target,
        status: workflowStatus?.brand_identity || "locked",
        items: [],
      },
      {
        title: "Go to Market",
        icon: TrendingUp,
        status: workflowStatus?.marketing_strategy || "locked",
        isExpandedByDefault: true,
        items: [
          {
            title: "Marketing Strategie",
            url: "/dashboard/go-to-market/marketing-strategy",
            status: workflowStatus?.marketing_strategy || "locked",
          },
          {
            title: "Online Presence",
            url: "/dashboard/go-to-market/online-presence",
            status: workflowStatus?.marketing_strategy || "locked",
          },
          {
            title: "Company Profile",
            url: "/dashboard/go-to-market/company-profile",
            status: workflowStatus?.marketing_strategy || "locked",
          }
        ],
      },

      {
        title: "Reach to Investors",
        icon: Presentation,
        status: workflowStatus?.marketing_strategy || "locked",
        isExpandedByDefault: true,
        items: [
          {
            title: "Contact",
            url: "/dashboard/reach-to-investors/contact",
            status: workflowStatus?.marketing_strategy || "locked",
          },
          {
            title: "Pitch Deck",
            url: "/dashboard/reach-to-investors/pitch-deck",
            status: workflowStatus?.marketing_strategy || "locked",
          }
        ],
      },
    ]
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
        <NavMain items={getNavData()} />

        {/* Marketing Analysis History — only rendered client-side to avoid SSR/localStorage mismatch */}
        {mounted && analysisHistory.length > 0 && (
          <SidebarGroup className="mt-2">
            <SidebarGroupLabel className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-muted-foreground px-2">
              <BarChart2 className="h-3.5 w-3.5" />
              Marketing
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu className="gap-0.5">
                {analysisHistory.slice(0, 6).map((item: any, idx: number) => (
                  <SidebarMenuItem key={`${item.id}-${idx}`}>
                    <SidebarMenuButton
                      onClick={() => { loadAnalysis(item); router.push('/dashboard') }}
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
