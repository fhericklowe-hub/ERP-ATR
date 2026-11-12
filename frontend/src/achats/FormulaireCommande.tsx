import { type FormEvent, useEffect, useState } from 'react'
import { api, type Page, type Service, type Site, type Tiers } from '../api'
import { type Commande, type LigneCommande, montant } from './commandes'
import type { Demande } from './types'

const ligneVide = (): LigneCommande => ({ reference: '', designation: '', quantite: '1', prix_unitaire: '', remise: '0', taux_tva: '18' })

type Saisie = Pick<Commande, 'fournisseur' | 'reference_fournisseur' | 'objet' | 'site' | 'service' | 'date_livraison'
  | 'transport' | 'adresse_livraison' | 'echeance' | 'mode_reglement' | 'ancien_numero' | 'lignes'>

const net = (l: LigneCommande) => Math.round((Number(l.prix_unitaire) || 0) * (1 - (Number(l.remise) || 0) / 100))
const ht = (l: LigneCommande) => Math.round((Number(l.quantite) || 0) * net(l))

/** Création depuis une demande d'achat (demandeId) ou correction d'un brouillon (id). */
export default function FormulaireCommande({ demandeId, id }: { demandeId?: number; id?: number }) {
  const [fournisseurs, setFournisseurs] = useState<Tiers[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [demande, setDemande] = useState<{ id: number; numero: string } | null>(null)
  const [c, setC] = useState<Saisie>({
    fournisseur: '', reference_fournisseur: '', objet: '', site: '', service: '', date_livraison: null,
    transport: 'PAR VOS SOINS', adresse_livraison: '', echeance: '30 JOURS FIN DE MOIS', mode_reglement: 'CHEQUE',
    ancien_numero: '', lignes: [ligneVide()],
  })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    Promise.all([
      api<Page<Tiers>>('/tiers/?est_fournisseur=true&actif=true'),
      api<Page<Site>>('/sites/?actif=true'),
      api<Page<Service>>('/services/?actif=true'),
      id ? api<Commande>(`/achats/bons-commande/${id}/`) : null,
      demandeId ? api<Demande>(`/achats/demandes/${demandeId}/`) : null,
    ])
      .then(([fo, si, se, bon, da]) => {
        setFournisseurs(fo.results)
        setSites(si.results)
        setServices(se.results)
        if (bon) {
          setC(bon)
          setDemande({ id: bon.demande, numero: bon.demande_numero })
        } else if (da) {
          // Le bon reprend le service, le site et les articles de la demande ; l'acheteur complète les prix.
          setDemande({ id: da.id, numero: da.numero })
          setC((x) => ({
            ...x, site: da.site, service: da.service,
            objet: da.equipement_designation || da.lignes[0]?.designation || '',
            lignes: da.lignes.map((l) => ({
              ...ligneVide(), reference: l.reference_constructeur, designation: l.designation, quantite: String(Number(l.quantite)),
            })),
          }))
        }
      })
      .catch((e: Error) => setErreur(e.message))
  }, [id, demandeId])

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setC((x) => ({ ...x, [k]: v }))
  const ligne = (i: number, k: keyof LigneCommande, v: string) =>
    setC((x) => ({ ...x, lignes: x.lignes.map((l, j) => (j === i ? { ...l, [k]: v } : l)) }))

  const totalHt = c.lignes.reduce((s, l) => s + ht(l), 0)
  const totalTva = c.lignes.reduce((s, l) => s + (ht(l) * (Number(l.taux_tva) || 0)) / 100, 0)

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!demande) return
    setEnCours(true)
    setErreur('')
    try {
      const corps = JSON.stringify({ ...c, demande: demande.id, date_livraison: c.date_livraison || null })
      const r = await api<Commande>(id ? `/achats/bons-commande/${id}/` : '/achats/bons-commande/', { method: id ? 'PUT' : 'POST', body: corps })
      location.hash = `#/commandes/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
      setEnCours(false)
    }
  }

  return (
    <form className="fiche" onSubmit={enregistrer}>
      <h2>{id ? 'Modifier le bon de commande' : 'Nouveau bon de commande'}</h2>
      {demande && <p>Pour la demande d'achat <a href={`#/demandes/${demande.id}`}>{demande.numero}</a></p>}

      <fieldset>
        <legend>Fournisseur</legend>
        <div className="grille">
          <label>Fournisseur
            <select required value={c.fournisseur} onChange={(e) => champ('fournisseur', Number(e.target.value))}>
              <option value="">Choisir…</option>
              {fournisseurs.map((f) => <option key={f.id} value={f.id}>{f.raison_sociale} ({f.code})</option>)}
            </select>
          </label>
          <label>N° de devis / commande fournisseur
            <input value={c.reference_fournisseur} onChange={(e) => champ('reference_fournisseur', e.target.value)} />
          </label>
          <label>Référence / objet
            <input value={c.objet} onChange={(e) => champ('objet', e.target.value)} />
          </label>
        </div>
        {fournisseurs.length === 0 && <p className="aide">Aucun fournisseur enregistré. Ils se créent dans l'administration, rubrique Tiers.</p>}
      </fieldset>

      <fieldset>
        <legend>Imputation et livraison</legend>
        <div className="grille">
          <label>Succursale
            <select required value={c.site} onChange={(e) => champ('site', Number(e.target.value))}>
              <option value="">Choisir…</option>
              {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
          <label>Service imputé
            <select required value={c.service} onChange={(e) => champ('service', Number(e.target.value))}>
              <option value="">Choisir…</option>
              {services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
          <label>Délai de livraison
            <input type="date" value={c.date_livraison ?? ''} onChange={(e) => champ('date_livraison', e.target.value)} />
          </label>
          <label>Transport
            <input value={c.transport} onChange={(e) => champ('transport', e.target.value)} />
          </label>
        </div>
        <label>Adresse de livraison
          <textarea value={c.adresse_livraison} onChange={(e) => champ('adresse_livraison', e.target.value)} />
        </label>
      </fieldset>

      <fieldset>
        <legend>Lignes</legend>
        {c.lignes.map((l, i) => (
          <div className="ligne commande" key={i}>
            <label>Référence
              <input value={l.reference} onChange={(e) => ligne(i, 'reference', e.target.value)} />
            </label>
            <label>Désignation
              <input required value={l.designation} onChange={(e) => ligne(i, 'designation', e.target.value)} />
            </label>
            <label>Qté
              <input required type="number" min="0.01" step="0.01" value={l.quantite} onChange={(e) => ligne(i, 'quantite', e.target.value)} />
            </label>
            <label>Prix unit. HT
              <input required type="number" min="0" step="1" value={l.prix_unitaire} onChange={(e) => ligne(i, 'prix_unitaire', e.target.value)} />
            </label>
            <label>Remise %
              <input type="number" min="0" max="100" step="0.01" value={l.remise} onChange={(e) => ligne(i, 'remise', e.target.value)} />
            </label>
            <label>TVA %
              <input type="number" min="0" max="100" step="0.01" value={l.taux_tva} onChange={(e) => ligne(i, 'taux_tva', e.target.value)} />
            </label>
            <div className="nombre"><span className="aide">Montant HT</span><br /><strong>{montant(ht(l))}</strong></div>
            {c.lignes.length > 1 && (
              <button type="button" className="discret" onClick={() => champ('lignes', c.lignes.filter((_, j) => j !== i))}>Retirer</button>
            )}
          </div>
        ))}
        <button type="button" className="secondaire" onClick={() => champ('lignes', [...c.lignes, ligneVide()])}>Ajouter une ligne</button>
        <p className="nombre">
          Total HT <strong>{montant(totalHt)}</strong> · TVA <strong>{montant(totalTva)}</strong> · Total TTC <strong>{montant(totalHt + Math.round(totalTva))} XOF</strong>
        </p>
      </fieldset>

      <fieldset>
        <legend>Règlement</legend>
        <div className="grille">
          <label>Échéance
            <input value={c.echeance} onChange={(e) => champ('echeance', e.target.value)} />
          </label>
          <label>Mode de règlement
            <select value={c.mode_reglement} onChange={(e) => champ('mode_reglement', e.target.value)}>
              <option value="CHEQUE">Chèque</option>
              <option value="VIREMENT">Virement</option>
              <option value="ESPECES">Espèces</option>
              <option value="TRAITE">Traite</option>
            </select>
          </label>
          <label>N° dans l'ancien logiciel (facultatif)
            <input value={c.ancien_numero} onChange={(e) => champ('ancien_numero', e.target.value)} />
          </label>
        </div>
      </fieldset>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours || !demande}>{enCours ? 'Enregistrement…' : 'Enregistrer le brouillon'}</button>
        <a href={id ? `#/commandes/${id}` : demande ? `#/demandes/${demande.id}` : '#/commandes'}>Annuler</a>
      </div>
    </form>
  )
}
