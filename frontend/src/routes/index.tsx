import { createFileRoute } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useState, useEffect } from 'react'

export const Route = createFileRoute('/')({ component: Dashboard })

function Dashboard() {
  const [modelCount, setModelCount] = useState<number>(0)
  const [artifactCount, setArtifactCount] = useState<number>(0)
  const [healthStatus, setHealthStatus] = useState<string>('Unknown')

  // Example: fetch data from API
  useEffect(() => {
    async function fetchData() {
      try {
        const healthRes = await fetch('/health')
        if (healthRes.ok) {
          setHealthStatus('OK')
        } else {
          setHealthStatus('Degraded')
        }

        const artifactsRes = await fetch('/artifacts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify([{ name: '*' }]),
        })
        if (artifactsRes.ok) {
          const data = await artifactsRes.json()
          setArtifactCount(data.length)
          setModelCount(data.filter((a: any) => a.type === 'model').length)
        }
      } catch (e) {
        setHealthStatus('Offline')
        console.error(e)
      }
    }

    fetchData()
  }, [])

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">ModelGuard Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>System Health</CardTitle>
          </CardHeader>
          <CardContent>
            <p>Status: <span className={`font-semibold ${healthStatus === 'OK' ? 'text-green-600' : healthStatus === 'Degraded' ? 'text-yellow-600' : 'text-red-600'}`}>{healthStatus}</span></p>
            <Button className="mt-4" onClick={() => window.location.reload()}>Refresh</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Artifacts</CardTitle>
          </CardHeader>
          <CardContent>
            <p>Total Artifacts: {artifactCount}</p>
            <p>Models: {modelCount}</p>
            <Separator className="my-2" />
            <Button onClick={() => alert('Navigate to artifact listing')}>View Artifacts</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button onClick={() => alert('Navigate to upload')}>Upload Model</Button>
            <Button onClick={() => alert('Navigate to rating')}>Rate Model</Button>
            <Button onClick={() => alert('Navigate to lineage')}>View Lineage</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
