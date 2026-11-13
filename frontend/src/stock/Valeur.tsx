import { useEffect, useState } from 'react'
import { api, type Page, telechargerFichier } from '../api'
import { montant } from '../achats/commandes'
import { dateFr } from '../achats/types'
import { type Magasin, nombre } from './types'

type Ligne = { article: number; code: string; designation: string; nature: string; unite: string; magasin: number; magasin_nom: string; quantite: string; cout_moyen: string | null; valeur: string | null }
type Etat = { date: string; count: number; total: string; sans_prix: number; results: Ligne[] }
type Consommations = {
  debut: string; fin: string; total: string; sans_prix: number
  par_service: { service: string; valeur: string }[]; par_or: { numero_or: string; materiel: string; valeur: string }[]
}

const jour = (d: Date) => d.toLocaleDateString('fr-CA')
const aujourdhui = () => jour(new Date())
const debutDuMois = () => { const d = new Date(); d.setDate(1); return jour(d) }

/** Stock valorisé au coût moyen pondéré, et valeur des sorties sur une période. */
export default function ValeurStock() {
  const [etat, setEtat] = useState<Etat | null>(null)
  const [conso, setConso] = useState<Consommations | null>(null)
  const [magasins, setMagasins] = useState<Magasin[]>([])
  const [filtre, setFiltre] = useState({ magasin: '', search: '', date: aujourdhui() })
  const [periode, setPeriode] = useState({ debut: debutDuMois(), fin: aujourdhui() })
  const [erreur, setErreur] = useState('')

  const requete = (valeurs: Record<string, string>) => new URLSearchParams(Object.entries(valeurs).filter(([, v]) => v))
  useEffect(() => {
    api<Page<Magasin>>('/emplacements/?type=SITE&actif=true').then((p) => setMagasins(p.results)).catch(() => undefined)
  }, [])
  useEffect(() => {
    if (!filtre.date) return
    setErreur('')
    api<Etat>(`/stock/valeur/?${requete(filtre)}`).then(setEtat).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(() => {
    if (!periode.debut || !periode.fin) return
    api<Consommations>(`/stock/consommations/?${requete({ ...periode, magasin: filtre.magasin })}`).then(setConso).catch(() => setConso(null))
  }, [periode, filtre.magasin])

  const exporter = () => telechargerFichier(`/stock/valeur/?${requete({ ...filtre, export: 'xlsx' })}`, `stock-valorise-${filtre.date}.xlsx`).catch((e: Error) => setErreur(e.message))
  return (
    <>
      <div className="barre">
        <h2>Valeur du stock</h2>
        <div className="actions"><button className="secondaire" onClick={exporter}>Exporter vers Excel</button></div>
      </div>
      <p className="aide">Le stock est valorisé au coût moyen pondéré : chaque entrée chiffrée (bon de réception, stock de départ) recalcule le coût moyen de l'article, et chaque sortie se fait à ce coût.</p>
      <div className="grille filtres large">
        <label>Magasin
          <select value={filtre.magasin} onChange={(e) => setFiltre({ ...filtre, magasin: e.target.value })}>
            <option value="">Tous</option>
            {magasins.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
          </select>
        </label>
        <label>Valeur au<input type="date" max={aujourdhui()} value={filtre.date} onChange={(e) => setFiltre({ ...filtre, date: e.target.value })} /></label>
        <label>Recherche<input placeholder="Code ou désignation" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {!etat && !erreur && <p>Chargement…</p>}
      {etat && (
        <>
          <p className="statut">Valeur au {dateFr(etat.date)} : {montant(etat.total)} XOF</p>
          {etat.sans_prix > 0 && <p className="aide">{etat.sans_prix} ligne{etat.sans_prix > 1 ? 's' : ''} sans coût connu (entrées jamais chiffrées) : elles ne sont pas comptées. Un ajustement d'inventaire avec un prix les corrige.</p>}
          {etat.count === 0 && <p className="aide">Rien en stock.</p>}
          {etat.count > 0 && (
            <div className="defilant">
              <table>
                <thead><tr><th>Code</th><th>Désignation</th><th>Magasin</th><th className="nombre">Quantité</th><th className="nombre">Coût moyen</th><th className="nombre">Valeur</th></tr></thead>
                <tbody>
                  {etat.results.map((l) => (
                    <tr key={`${l.article}-${l.magasin}`}>
                      <td>{l.code}</td><td>{l.designation}<br /><span className="aide">{l.nature}</span></td><td>{l.magasin_nom}</td>
                      <td className="nombre">{nombre(l.quantite)} {l.unite}</td>
                      <td className="nombre">{l.cout_moyen === null ? <span className="aide">inconnu</span> : montant(l.cout_moyen)}</td>
                      <td className="nombre">{l.valeur === null ? '' : montant(l.valeur)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {etat.count > etat.results.length && <p className="aide">Seules les {etat.results.length} premières lignes sont affichées ; l'export Excel les contient toutes.</p>}
        </>
      )}

      <h3>Sorties de stock valorisées</h3>
      <div className="grille filtres">
        <label>Du<input type="date" max={periode.fin} value={periode.debut} onChange={(e) => setPeriode({ ...periode, debut: e.target.value })} /></label>
        <label>Au<input type="date" min={periode.debut} max={aujourdhui()} value={periode.fin} onChange={(e) => setPeriode({ ...periode, fin: e.target.value })} /></label>
      </div>
      {conso && (
        <>
          <p className="statut">Sorti sur la période : {montant(conso.total)} XOF</p>
          {conso.sans_prix > 0 && <p className="aide">{conso.sans_prix} sortie{conso.sans_prix > 1 ? 's' : ''} d'articles sans coût connu ne sont pas comptées.</p>}
          <div className="grille">
            <div className="defilant">
              <table>
                <thead><tr><th>Service</th><th className="nombre">Valeur</th></tr></thead>
                <tbody>
                  {conso.par_service.map((s) => <tr key={s.service}><td>{s.service}</td><td className="nombre">{montant(s.valeur)}</td></tr>)}
                  {conso.par_service.length === 0 && <tr><td colSpan={2} className="aide">Aucune sortie.</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="defilant">
              <table>
                <thead><tr><th>Ordre de réparation</th><th className="nombre">Valeur</th></tr></thead>
                <tbody>
                  {conso.par_or.map((o) => <tr key={o.numero_or}><td>{o.numero_or}{o.materiel && <><br /><span className="aide">{o.materiel}</span></>}</td><td className="nombre">{montant(o.valeur)}</td></tr>)}
                  {conso.par_or.length === 0 && <tr><td colSpan={2} className="aide">Aucune sortie pour un OR.</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  )
}
