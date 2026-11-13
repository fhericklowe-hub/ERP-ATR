import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import BoutonExcel from '../BoutonExcel'

type Article = {
  id: number; code: string; designation: string; nature: string; nature_libelle: string; famille: number | null; famille_nom: string
  unite: number | ''; unite_code: string; gere_en_stock: boolean; actif: boolean
}
type Saisie = Pick<Article, 'code' | 'designation' | 'nature' | 'famille' | 'unite' | 'gere_en_stock' | 'actif'> & { id?: number }
type Choix = { id: number; code: string; nom: string }

const NATURES = [['PIECE', 'Pièce détachée'], ['CONSO', 'Consommable'], ['FOURN', 'Fourniture'], ['SERVICE', 'Service'], ['IMMO', 'Immobilisation']]
const VIDE: Saisie = { code: '', designation: '', nature: 'PIECE', famille: null, unite: '', gere_en_stock: true, actif: true }

/** Le catalogue : tout ce qui s'achète ou se stocke. Un article ne se supprime pas, il se désactive. */
export default function Articles({ peutCreer, peutModifier }: { peutCreer: boolean; peutModifier: boolean }) {
  const [liste, setListe] = useState<Article[] | null>(null)
  const [total, setTotal] = useState(0)
  const [filtre, setFiltre] = useState({ search: '', nature: '', actif: 'true' })
  const [fiche, setFiche] = useState<Saisie | null>(null)
  const [unites, setUnites] = useState<Choix[]>([])
  const [familles, setFamilles] = useState<Choix[]>([])
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    const q = new URLSearchParams({ search: filtre.search, page_size: '200' })
    if (filtre.nature) q.set('nature', filtre.nature)
    if (filtre.actif) q.set('actif', filtre.actif)
    api<Page<Article>>(`/articles/?${q}`).then((p) => { setListe(p.results); setTotal(p.count) }).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Choix>>('/unites/?page_size=200').then((p) => setUnites(p.results)).catch(() => undefined)
    if (peutCreer || peutModifier) api<Page<Choix>>('/familles-articles/?page_size=200').then((p) => setFamilles(p.results)).catch(() => undefined)
  }, [peutCreer, peutModifier])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!fiche) return
    setErreur('')
    setEnCours(true)
    try {
      const { id, ...corps } = fiche
      await api(id ? `/articles/${id}/` : '/articles/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps) })
      setFiche(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  if (fiche) {
    return (
      <form className="fiche" onSubmit={enregistrer}>
        <p><a href="#/articles" onClick={() => setFiche(null)}>← Articles</a></p>
        <h2>{fiche.id ? `${fiche.code} · ${fiche.designation}` : 'Nouvel article'}</h2>
        <fieldset>
          <div className="grille">
            <label>Code<input required maxLength={30} autoFocus={!fiche.id} value={fiche.code} onChange={(e) => setFiche({ ...fiche, code: e.target.value })} /></label>
            <label>Désignation<input required maxLength={200} value={fiche.designation} onChange={(e) => setFiche({ ...fiche, designation: e.target.value })} /></label>
            <label>Nature
              <select value={fiche.nature} onChange={(e) => setFiche({ ...fiche, nature: e.target.value })}>{NATURES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
            </label>
            <label>Unité
              <select required value={fiche.unite} onChange={(e) => setFiche({ ...fiche, unite: Number(e.target.value) || '' })}>
                <option value="">Choisir</option>{unites.map((u) => <option key={u.id} value={u.id}>{u.code} · {u.nom}</option>)}
              </select>
            </label>
            {familles.length > 0 && (
              <label>Famille
                <select value={fiche.famille ?? ''} onChange={(e) => setFiche({ ...fiche, famille: Number(e.target.value) || null })}>
                  <option value="">Aucune</option>{familles.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
                </select>
              </label>
            )}
          </div>
          <label className="case"><input type="checkbox" checked={fiche.gere_en_stock} onChange={(e) => setFiche({ ...fiche, gere_en_stock: e.target.checked })} /> Géré en stock (décoché : s'achète sans entrer au magasin)</label>
          {fiche.id && <label className="case"><input type="checkbox" checked={fiche.actif} onChange={(e) => setFiche({ ...fiche, actif: e.target.checked })} /> Actif (décoché : n'est plus proposé dans les listes)</label>}
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button type="button" className="secondaire" onClick={() => { setFiche(null); setErreur('') }}>Annuler</button>
          <button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      </form>
    )
  }

  return (
    <>
      <div className="barre">
        <h2>Articles</h2>
        <div className="actions">
          <BoutonExcel chemin="/articles/" nom="articles" filtres={{ search: filtre.search, nature: filtre.nature, actif: filtre.actif }} onErreur={setErreur} />
          {peutCreer && <button onClick={() => { setErreur(''); setFiche(VIDE) }}>Nouvel article</button>}
        </div>
      </div>
      <div className="grille filtres">
        <label>Recherche<input placeholder="Code ou désignation" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Nature
          <select value={filtre.nature} onChange={(e) => setFiltre({ ...filtre, nature: e.target.value })}><option value="">Toutes</option>{NATURES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>
        </label>
        <label>Situation
          <select value={filtre.actif} onChange={(e) => setFiltre({ ...filtre, actif: e.target.value })}><option value="true">Actifs</option><option value="false">Désactivés</option><option value="">Tous</option></select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucun article.</p>}
      {liste && liste.length > 0 && (
        <>
          <p className="aide">{total} article{total > 1 ? 's' : ''}{total > liste.length ? ` · les ${liste.length} premiers sont affichés, précisez la recherche` : ''}</p>
          <div className="defilant">
            <table>
              <thead><tr><th>Code</th><th>Désignation</th><th>Nature</th><th>Famille</th><th>Unité</th><th>En stock</th><th></th></tr></thead>
              <tbody>
                {liste.map((x) => (
                  <tr key={x.id}>
                    <td>{x.code}</td>
                    <td>{x.designation}{!x.actif && <> <span className="pastille">Désactivé</span></>}</td>
                    <td>{x.nature_libelle}</td><td>{x.famille_nom}</td><td>{x.unite_code}</td><td>{x.gere_en_stock ? 'Oui' : 'Non'}</td>
                    <td>{peutModifier && <button className="secondaire" onClick={() => { setErreur(''); setFiche({ id: x.id, code: x.code, designation: x.designation, nature: x.nature, famille: x.famille, unite: x.unite, gere_en_stock: x.gere_en_stock, actif: x.actif }) }}>Modifier</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
