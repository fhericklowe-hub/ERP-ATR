import { type FormEvent, useEffect, useState } from 'react'
import Detail from './achats/Detail'
import DetailBudget from './achats/DetailBudget'
import FormulaireBudget from './achats/FormulaireBudget'
import ListeBudget from './achats/ListeBudget'
import DetailCommande from './achats/DetailCommande'
import FormulaireCommande from './achats/FormulaireCommande'
import ListeCommandes from './achats/ListeCommandes'
import DetailReception from './achats/DetailReception'
import FormulaireReception from './achats/FormulaireReception'
import ListeReceptions from './achats/ListeReceptions'
import Formulaire from './achats/Formulaire'
import Liste from './achats/Liste'
import { DetailSortie, FormulaireSortie, ListeSorties } from './stock/Sorties'
import { DetailDemande, FormulaireDemande, ListeDemandes } from './stock/Demandes'
import ImportStock from './stock/ImportStock'
import { DetailOrdre, FormulaireOrdre, ListeOrdres } from './technique/Ordres'
import { DetailDevis, FormulaireDevis, ListeDevis } from './commercial/Devis'
import { DetailMise, ListeMises } from './exploitation/Mises'
import { DetailReleve, ListeReleves } from './exploitation/Releves'
import Entretien from './technique/Entretien'
import HistoriqueMateriel from './technique/Historique'
import ImportParc from './technique/ImportParc'
import Parc from './technique/Parc'
import Accueil from './Accueil'
import Pilotage from './Pilotage'
import Comptes from './Comptes'
import Epi from './hse/Epi'
import { DetailEvenement, FormulaireEvenement, ListeEvenements } from './hse/Evenements'
import { DetailVisite, FormulaireVisite, ListeVisites } from './hse/Visites'
import { DetailAbsence, FormulaireAbsence, ListeAbsences, PlanningAbsences } from './rh/Absences'
import ImportPersonnel from './rh/ImportPersonnel'
import { ImportTiers, ListeTiers } from './referentiels/Tiers'
import Articles from './referentiels/Articles'
import { DetailSalarie, EcheancesPersonnel, FormulaireSalarie, ListeSalaries } from './rh/Personnel'
import Stock from './stock/Stock'
import ValeurStock from './stock/Valeur'
import Biens from './moyens/Biens'
import Contrats from './moyens/Contrats'
import Echeances from './moyens/Echeances'
import DetailIntervention from './moyens/DetailIntervention'
import FormulaireIntervention from './moyens/FormulaireIntervention'
import ListeInterventions from './moyens/ListeInterventions'
import { api, connecter, deconnecter, estConnecte, type Utilisateur } from './api'

function Connexion({ onConnecte }: { onConnecte: () => void }) {
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  async function envoyer(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setEnCours(true)
    setErreur('')
    try {
      await connecter(String(f.get('username')), String(f.get('password')))
      onConnecte()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <main className="connexion">
      <form onSubmit={envoyer}>
        <img src="/logo.png" alt="ATR" width="180" />
        <h1>ERP</h1>
        <label>
          Identifiant
          <input name="username" autoComplete="username" required autoFocus />
        </label>
        <label>
          Mot de passe
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <button disabled={enCours}>{enCours ? 'Connexion…' : 'Se connecter'}</button>
      </form>
    </main>
  )
}

type Lien = { chemin: string; texte: string; droit: string; aussi?: string[] }
/** Le menu : un onglet par module, et sous chaque onglet ses rubriques. `aussi` : autres adresses de la même rubrique. */
const MENU: { titre: string; liens: Lien[] }[] = [
  { titre: 'Direction', liens: [
    { chemin: '/pilotage', texte: 'Tableau de bord', droit: 'core.voir_pilotage' },
  ] },
  { titre: 'Achats', liens: [
    { chemin: '/', texte: "Demandes d'achat", droit: 'achats.view_demandeachat', aussi: ['/demandes'] },
    { chemin: '/budget', texte: 'Demandes liées au budget', droit: 'achats.view_demandebudget' },
    { chemin: '/commandes', texte: 'Bons de commande', droit: 'achats.view_boncommande' },
    { chemin: '/receptions', texte: 'Bons de réception', droit: 'achats.view_bonreception' },
    { chemin: '/fournisseurs', texte: 'Fournisseurs', droit: 'achats.view_boncommande' },
  ] },
  { titre: 'Stock', liens: [
    { chemin: '/stock/demandes', texte: 'Demandes de sortie', droit: 'stock.view_demandesortie' },
    { chemin: '/stock', texte: 'État du stock', droit: 'stock.view_mouvement', aussi: ['/stock/import'] },
    { chemin: '/stock/sorties', texte: 'Bons de sortie', droit: 'stock.view_bonsortie' },
    { chemin: '/stock/valeur', texte: 'Valeur du stock', droit: 'stock.voir_valeur_stock' },
    { chemin: '/articles', texte: 'Articles', droit: 'referentiels.change_article' },
  ] },
  { titre: 'Technique', liens: [
    { chemin: '/parc', texte: 'Parc de matériels', droit: 'technique.view_materiel' },
    { chemin: '/ordres', texte: 'Ordres de réparation', droit: 'technique.view_ordrereparation' },
    { chemin: '/entretien', texte: 'Entretien préventif', droit: 'technique.view_planentretien' },
  ] },
  { titre: 'Commercial', liens: [
    { chemin: '/devis', texte: 'Devis de location', droit: 'commercial.view_devis' },
    { chemin: '/releves', texte: 'Relevés de location', droit: 'exploitation.view_relevelocation' },
    { chemin: '/clients', texte: 'Clients', droit: 'commercial.view_devis' },
  ] },
  { titre: 'Exploitation', liens: [
    { chemin: '/mises', texte: 'Mises à disposition', droit: 'exploitation.view_miseadisposition' },
  ] },
  { titre: 'RH', liens: [
    { chemin: '/personnel', texte: 'Personnel', droit: 'rh.view_salarie' },
    { chemin: '/personnel/echeances', texte: 'Échéances', droit: 'rh.view_salarie' },
    { chemin: '/absences', texte: 'Congés et absences', droit: 'rh.view_demandeabsence' },
    { chemin: '/absences/planning', texte: 'Planning des absences', droit: 'rh.view_demandeabsence' },
  ] },
  { titre: 'HSE', liens: [
    { chemin: '/hse', texte: 'Événements', droit: 'hse.view_evenement' },
    { chemin: '/hse/visites', texte: 'Visites de sécurité', droit: 'hse.view_visite' },
    { chemin: '/hse/epi', texte: 'Équipements de protection', droit: 'hse.view_dotationepi' },
  ] },
  { titre: 'Moyens généraux', liens: [
    { chemin: '/interventions', texte: 'Interventions', droit: 'moyens.view_demandeintervention' },
    { chemin: '/biens', texte: 'Biens', droit: 'moyens.view_bien' },
    { chemin: '/echeances', texte: 'Échéances', droit: 'moyens.view_echeance' },
    { chemin: '/contrats', texte: 'Contrats', droit: 'moyens.view_contrat' },
  ] },
  { titre: 'Administration', liens: [
    { chemin: '/comptes', texte: 'Comptes', droit: 'core.gerer_comptes' },
  ] },
]

/** La rubrique à laquelle appartient une adresse : la plus précise de celles dont l'adresse commence pareil. */
function rubrique(chemin: string): Lien | undefined {
  const debute = (base: string) => chemin === base || (base !== '/' && chemin.startsWith(`${base}/`))
  return MENU.flatMap((m) => m.liens)
    .filter((l) => debute(l.chemin) || (l.aussi ?? []).some(debute))
    .sort((x, y) => y.chemin.length - x.chemin.length)[0]
}

function useRoute() {
  const [hash, setHash] = useState(location.hash)
  useEffect(() => {
    const maj = () => setHash(location.hash)
    addEventListener('hashchange', maj)
    return () => removeEventListener('hashchange', maj)
  }, [])
  return hash.replace(/^#/, '') || '/accueil'
}

function Page({ moi, route }: { moi: Utilisateur; route: string }) {
  const a = (droit: string) => moi.droits.includes(droit)
  if (route === '/accueil') return <Accueil moi={moi} />
  if (route === '/comptes') return a('core.gerer_comptes') ? <Comptes moi={moi.id} /> : <p>Cette page est réservée à ceux qui gèrent les comptes.</p>
  if (route === '/pilotage') return a('core.voir_pilotage') ? <Pilotage /> : <p>Cette page est réservée à la direction.</p>
  if (route === '/interventions') return <ListeInterventions />
  if (route === '/interventions/nouvelle') return <FormulaireIntervention moi={moi} />
  const modifInt = route.match(/^\/interventions\/(\d+)\/modifier$/)
  if (modifInt) return <FormulaireIntervention moi={moi} id={Number(modifInt[1])} />
  const intervention = route.match(/^\/interventions\/(\d+)$/)
  if (intervention) return <DetailIntervention id={Number(intervention[1])} />
  if (route === '/stock') return <Stock />
  const [chemin, requete] = route.split('?')
  const param = (nom: string) => new URLSearchParams(requete ?? '').get(nom) ?? undefined
  if (chemin === '/parc') return <Parc peutModifier={a('technique.change_materiel')} />
  if (chemin === '/devis') return <ListeDevis peutCreer={a('commercial.add_devis')} />
  if (chemin === '/devis/nouveau') return <FormulaireDevis />
  const modifDevis = chemin.match(/^\/devis\/(\d+)\/modifier$/)
  if (modifDevis) return <FormulaireDevis id={Number(modifDevis[1])} />
  const devis = chemin.match(/^\/devis\/(\d+)$/)
  if (devis) return <DetailDevis id={Number(devis[1])} voitMises={a('exploitation.view_miseadisposition')} peutPreparer={a('exploitation.add_miseadisposition')} voitReleves={a('exploitation.view_relevelocation')} peutRelever={a('exploitation.add_relevelocation')} />
  if (chemin === '/hse') return <ListeEvenements peutTraiter={a('hse.traiter_evenement')} />
  if (chemin === '/hse/nouveau') return <FormulaireEvenement />
  if (chemin === '/hse/epi') return <Epi peutModifier={a('hse.add_dotationepi')} />
  if (chemin === '/hse/visites') return <ListeVisites peutCreer={a('hse.add_visite')} />
  if (chemin === '/hse/visites/nouvelle') return <FormulaireVisite />
  const modifVisite = chemin.match(/^\/hse\/visites\/(\d+)\/modifier$/)
  if (modifVisite) return <FormulaireVisite id={Number(modifVisite[1])} />
  const visite = chemin.match(/^\/hse\/visites\/(\d+)$/)
  if (visite) return <DetailVisite id={Number(visite[1])} />
  const modifHse = chemin.match(/^\/hse\/(\d+)\/modifier$/)
  if (modifHse) return <FormulaireEvenement id={Number(modifHse[1])} />
  const evenement = chemin.match(/^\/hse\/(\d+)$/)
  if (evenement) return <DetailEvenement id={Number(evenement[1])} />
  if (chemin === '/absences') return <ListeAbsences voitTout={a('rh.approuver_demandeabsence') || a('rh.view_salarie')} />
  if (chemin === '/absences/planning') return <PlanningAbsences />
  if (chemin === '/absences/nouvelle') return <FormulaireAbsence pourAutrui={a('rh.approuver_demandeabsence')} />
  const absence = chemin.match(/^\/absences\/(\d+)$/)
  if (absence) return <DetailAbsence id={Number(absence[1])} />
  if (chemin === '/personnel') return <ListeSalaries peutCreer={a('rh.add_salarie')} />
  if (chemin === '/personnel/echeances') return <EcheancesPersonnel />
  if (chemin === '/personnel/nouveau') return <FormulaireSalarie />
  if (chemin === '/personnel/import') return a('rh.add_salarie') ? <ImportPersonnel /> : <p>L'import est réservé au gestionnaire RH.</p>
  const modifSalarie = chemin.match(/^\/personnel\/(\d+)\/modifier$/)
  if (modifSalarie) return <FormulaireSalarie id={Number(modifSalarie[1])} />
  const salarie = chemin.match(/^\/personnel\/(\d+)$/)
  if (salarie) return <DetailSalarie id={Number(salarie[1])} />
  for (const qualite of ['fournisseur', 'client'] as const) {
    if (chemin === `/${qualite}s`) return <ListeTiers key={qualite} qualite={qualite} peutCreer={a('referentiels.add_tiers')} peutModifier={a('referentiels.change_tiers')} />
    if (chemin === `/${qualite}s/import`) return a('referentiels.add_tiers') ? <ImportTiers key={qualite} qualite={qualite} /> : <p>L'import est réservé à ceux qui créent les fiches.</p>
  }
  if (chemin === '/articles') return <Articles peutCreer={a('referentiels.add_article')} peutModifier={a('referentiels.change_article')} />
  if (chemin === '/releves') return <ListeReleves />
  const releve = chemin.match(/^\/releves\/(\d+)$/)
  if (releve) return <DetailReleve id={Number(releve[1])} />
  if (chemin === '/mises') return <ListeMises />
  const mise = chemin.match(/^\/mises\/(\d+)$/)
  if (mise) return <DetailMise id={Number(mise[1])} peutOuvrirOr={a('technique.add_ordrereparation')} />
  if (chemin === '/parc/import') return <ImportParc />
  const materiel = chemin.match(/^\/parc\/(\d+)$/)
  if (materiel) return <HistoriqueMateriel seul id={Number(materiel[1])} />
  if (chemin === '/entretien') return <Entretien peutModifier={a('technique.change_planentretien')} peutOuvrir={a('technique.add_ordrereparation')} />
  if (chemin === '/ordres') return <ListeOrdres key={route} materiel={param('materiel')} peutCreer={a('technique.add_ordrereparation')} />
  if (chemin === '/ordres/nouveau') return <FormulaireOrdre materiel={param('materiel')} />
  const ordre = chemin.match(/^\/ordres\/(\d+)$/)
  if (ordre) return <DetailOrdre id={Number(ordre[1])} peutDemanderPieces={a('stock.add_demandesortie')} />
  if (route === '/stock/demandes') return <ListeDemandes />
  if (chemin === '/stock/demandes/nouvelle') return <FormulaireDemande moi={moi} numeroOr={param('or')} materiel={param('materiel')} />
  const demandeSortie = route.match(/^\/stock\/demandes\/(\d+)$/)
  if (demandeSortie) return <DetailDemande id={Number(demandeSortie[1])} />
  if (route === '/stock/import') return <ImportStock />
  if (route === '/stock/valeur') return <ValeurStock />
  if (route === '/stock/sorties') return <ListeSorties peutSortir={a('stock.add_bonsortie')} />
  if (route === '/stock/sorties/nouvelle') return <FormulaireSortie />
  const sortie = route.match(/^\/stock\/sorties\/(\d+)$/)
  if (sortie) return <DetailSortie id={Number(sortie[1])} />
  if (route === '/echeances') return <Echeances />
  if (route === '/contrats') return <Contrats />
  if (route === '/biens') return <Biens peutModifier={a('moyens.change_bien')} />
  if (route === '/' && !a('achats.view_demandeachat')) {
    // Sans accès aux demandes d'achat, l'accueil est la première rubrique à laquelle l'utilisateur a droit.
    const premiere = MENU.flatMap((m) => m.liens).find((l) => a(l.droit))
    if (!premiere) return <p>Aucune rubrique ne vous est ouverte pour l'instant. Demandez vos droits à l'administrateur.</p>
    location.replace(`#${premiere.chemin}`)
    return null
  }
  if (route === '/demandes/nouvelle') return <Formulaire moi={moi} />
  const modif = route.match(/^\/demandes\/(\d+)\/modifier$/)
  if (modif) return <Formulaire moi={moi} id={Number(modif[1])} />
  const detail = route.match(/^\/demandes\/(\d+)$/)
  if (detail) return <Detail id={Number(detail[1])} moiId={moi.id} droits={moi.droits} />
  if (route.split('?')[0] === '/commandes') return <ListeCommandes key={route} />
  if (route === '/receptions') return <ListeReceptions />
  if (route === '/budget') return <ListeBudget />
  if (route === '/budget/nouvelle') return <FormulaireBudget moi={moi} />
  const modifBudget = route.match(/^\/budget\/(\d+)\/modifier$/)
  if (modifBudget) return <FormulaireBudget moi={moi} id={Number(modifBudget[1])} />
  const bonBudget = route.match(/^\/budget\/(\d+)\/commander$/)
  if (bonBudget) return <FormulaireCommande budgetId={Number(bonBudget[1])} />
  const budget = route.match(/^\/budget\/(\d+)$/)
  if (budget) return <DetailBudget id={Number(budget[1])} />
  const recevoir = route.match(/^\/commandes\/(\d+)\/recevoir$/)
  if (recevoir) return <FormulaireReception commandeId={Number(recevoir[1])} />
  const modifBr = route.match(/^\/receptions\/(\d+)\/modifier$/)
  if (modifBr) return <FormulaireReception id={Number(modifBr[1])} />
  const br = route.match(/^\/receptions\/(\d+)$/)
  if (br) return <DetailReception id={Number(br[1])} />
  const nouveauBon = route.match(/^\/demandes\/(\d+)\/commander$/)
  if (nouveauBon) return <FormulaireCommande demandeId={Number(nouveauBon[1])} />
  const modifBon = route.match(/^\/commandes\/(\d+)\/modifier$/)
  if (modifBon) return <FormulaireCommande id={Number(modifBon[1])} />
  const bon = route.match(/^\/commandes\/(\d+)$/)
  if (bon) return <DetailCommande id={Number(bon[1])} />
  return <Liste />
}

export default function App() {
  const [connecte, setConnecte] = useState(estConnecte())
  const [moi, setMoi] = useState<Utilisateur | null>(null)
  const route = useRoute()

  useEffect(() => {
    if (!connecte) return
    api<Utilisateur>('/moi/')
      .then(setMoi)
      .catch(() => setConnecte(false))
  }, [connecte])

  if (!connecte) return <Connexion onConnecte={() => setConnecte(true)} />

  function quitter() {
    deconnecter()
    setMoi(null)
    setConnecte(false)
  }

  const a = (droit: string) => !!moi && moi.droits.includes(droit)
  const active = rubrique(route.split('?')[0])
  const modules = MENU.map((m) => ({ ...m, liens: m.liens.filter((l) => a(l.droit)) })).filter((m) => m.liens.length > 0)
  const moduleActif = modules.find((m) => m.liens.some((l) => l.chemin === active?.chemin))

  return (
    <>
      <header>
        <a href="#/accueil" className="marque" title="Accueil"><img src="/logo.png" alt="ATR" height="36" /><strong>ERP</strong></a>
        <nav aria-label="Modules">
          {modules.map((m) => (
            <a key={m.titre} href={`#${m.liens[0].chemin}`} aria-current={m === moduleActif ? 'page' : undefined}>{m.titre}</a>
          ))}
        </nav>
        <span>{moi ? `${moi.first_name} ${moi.last_name}`.trim() || moi.username : ''}</span>
        <button onClick={quitter}>Se déconnecter</button>
      </header>
      {moduleActif && moduleActif.liens.length > 1 && (
        <nav className="rubriques" aria-label={moduleActif.titre}>
          {moduleActif.liens.map((l) => (
            <a key={l.chemin} href={`#${l.chemin}`} aria-current={l.chemin === active?.chemin ? 'page' : undefined}>{l.texte}</a>
          ))}
        </nav>
      )}
      <main>
        {moi && <Page moi={moi} route={route} />}
      </main>
    </>
  )
}
