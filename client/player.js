// client/player.js - Refined Native Audio Engine (YouTube & Spotify Streaming)

(function () {
  'use strict';

  // State Management
  const state = {
    activeSource: 'youtube', // 'youtube' | 'spotify'
    activeTab: 'discover',   // 'discover' | 'queue' | 'liked' | 'pl_...'
    activePlaylistId: null,
    currentList: [],
    queue: [],
    history: [],
    likedSongs: [],          // Array of track objects
    playlists: [],           // Array of { id, name, createdAt, tracks: [...] }
    currentIndex: -1,
    isPlaying: false,
    isMuted: false,
    previousVolume: 80,
    volume: 80,
    isLooping: false,
    isShuffling: false,
    currentTrack: null,
    isScrubbing: false,
    modalTargetTrack: null,
    activeCategory: 'all',
    discoverData: null
  };

  const STORAGE_KEYS = {
    LIKED: 'tubefast_liked_songs',
    PLAYLISTS: 'tubefast_playlists'
  };

  // Dual-Deck Gapless Audio Elements
  const deckA = document.getElementById('deckA') || document.getElementById('audioEngine');
  const deckB = document.getElementById('deckB') || document.createElement('audio');
  let currentDeck = deckA;
  let standbyDeck = deckB;
  let preloadedTrack = null;
  let isStandbyReady = false;
  const deadTracksSet = new Set();

  // DOM Elements
  const elements = {
    get audioEngine() { return currentDeck; },
    sourceBtnYouTube: document.getElementById('sourceBtnYouTube'),
    sourceBtnSpotify: document.getElementById('sourceBtnSpotify'),
    searchInput: document.getElementById('searchInput'),
    searchClearBtn: document.getElementById('searchClearBtn'),
    searchSubmitBtn: document.getElementById('searchSubmitBtn'),
    trackListContainer: document.getElementById('trackListContainer'),
    categoryPillBar: document.getElementById('categoryPillBar'),
    loader: document.getElementById('loader'),
    loaderText: document.getElementById('loaderText'),
    viewTitle: document.getElementById('viewTitle'),
    viewSubtitle: document.getElementById('viewSubtitle'),
    clearQueueBtn: document.getElementById('clearQueueBtn'),
    playlistPlayAllBtn: document.getElementById('playlistPlayAllBtn'),
    deletePlaylistBtn: document.getElementById('deletePlaylistBtn'),
    queueBadge: document.getElementById('queueBadge'),
    likedBadge: document.getElementById('likedBadge'),
    playlistsList: document.getElementById('playlistsList'),
    sidebarCreatePlaylistBtn: document.getElementById('sidebarCreatePlaylistBtn'),
    engineBadge: document.getElementById('engineBadge'),
    pipelineStatus: document.getElementById('pipelineStatus'),
    equalizerVisualizer: document.getElementById('equalizerVisualizer'),
    // Bottom Player Elements
    trackCover: document.getElementById('trackCover'),
    trackSourceTag: document.getElementById('trackSourceTag'),
    trackName: document.getElementById('trackName'),
    trackArtist: document.getElementById('trackArtist'),
    nowPlayingLikeBtn: document.getElementById('nowPlayingLikeBtn'),
    playPauseBtn: document.getElementById('playPauseBtn'),
    playIcon: document.getElementById('playIcon'),
    pauseIcon: document.getElementById('pauseIcon'),
    prevBtn: document.getElementById('prevBtn'),
    nextBtn: document.getElementById('nextBtn'),
    shuffleBtn: document.getElementById('shuffleBtn'),
    loopBtn: document.getElementById('loopBtn'),
    progressBar: document.getElementById('progressBar'),
    currentTimeLabel: document.getElementById('currentTime'),
    totalTimeLabel: document.getElementById('totalTime'),
    volumeBar: document.getElementById('volumeBar'),
    muteBtn: document.getElementById('muteBtn'),
    volIcon: document.getElementById('volIcon'),
    navItems: document.querySelectorAll('.nav-item'),
    // Modals
    createPlaylistModal: document.getElementById('createPlaylistModal'),
    playlistNameInput: document.getElementById('playlistNameInput'),
    confirmCreatePlaylistBtn: document.getElementById('confirmCreatePlaylistBtn'),
    cancelCreatePlaylistBtn: document.getElementById('cancelCreatePlaylistBtn'),
    closeCreatePlaylistModal: document.getElementById('closeCreatePlaylistModal'),
    addToPlaylistModal: document.getElementById('addToPlaylistModal'),
    modalTargetTrackSummary: document.getElementById('modalTargetTrackSummary'),
    modalPlaylistSelectList: document.getElementById('modalPlaylistSelectList'),
    modalNewPlaylistBtn: document.getElementById('modalNewPlaylistBtn'),
    modalDoneBtn: document.getElementById('modalDoneBtn'),
    closeAddToPlaylistModal: document.getElementById('closeAddToPlaylistModal'),
    // Window Controls
    winMinBtn: document.getElementById('winMinBtn'),
    winMaxBtn: document.getElementById('winMaxBtn'),
    winCloseBtn: document.getElementById('winCloseBtn'),
    topNav: document.querySelector('.top-nav')
  };

  // Persistent Disk & Local Storage Sync
  let libraryLoadedFromDisk = false;
  let saveDiskTimeout = null;
  function scheduleSaveLibraryToDisk() {
    clearTimeout(saveDiskTimeout);
    saveDiskTimeout = setTimeout(() => {
      saveLibraryToDiskNow();
    }, 200);
  }

  function saveLibraryToDiskNow() {
    if (!libraryLoadedFromDisk) return;
    const payload = JSON.stringify({
      liked: state.likedSongs,
      playlists: state.playlists
    });
    fetch('/api/library', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload
    }).catch(err => {
      console.warn('Could not sync library to disk:', err);
    });
  }

  function loadSavedData() {
    // 1. Instant local storage read for snappy initial paint
    let localLiked = [];
    let localPlaylists = [];
    try {
      const rawLiked = localStorage.getItem(STORAGE_KEYS.LIKED);
      if (rawLiked) localLiked = JSON.parse(rawLiked);
    } catch (e) {}
    try {
      const rawPlaylists = localStorage.getItem(STORAGE_KEYS.PLAYLISTS);
      if (rawPlaylists) localPlaylists = JSON.parse(rawPlaylists);
    } catch (e) {}

    state.likedSongs = Array.isArray(localLiked) ? localLiked : [];
    state.playlists = Array.isArray(localPlaylists) ? localPlaylists : [];
    updateLikedBadge();
    renderPlaylistsSidebar();

    // 2. Fetch authoritative persistent library from disk
    fetch('/api/library')
      .then(res => res.json())
      .then(data => {
        libraryLoadedFromDisk = true;
        if (data && Array.isArray(data.liked)) {
          state.likedSongs = data.liked;
        }
        if (data && Array.isArray(data.playlists)) {
          state.playlists = data.playlists;
        }
        try {
          localStorage.setItem(STORAGE_KEYS.LIKED, JSON.stringify(state.likedSongs));
          localStorage.setItem(STORAGE_KEYS.PLAYLISTS, JSON.stringify(state.playlists));
        } catch (e) {}
        updateLikedBadge();
        renderPlaylistsSidebar();
        if (state.activeTab === 'liked') {
          renderLikedSongsView();
        } else if (state.activeTab && state.activeTab.startsWith('pl_')) {
          renderPlaylistView(state.activeTab);
        }
      })
      .catch(err => {
        libraryLoadedFromDisk = true;
        console.warn('Disk library fetch fallback:', err);
      });
  }

  function saveLikedSongs() {
    try {
      localStorage.setItem(STORAGE_KEYS.LIKED, JSON.stringify(state.likedSongs));
    } catch (e) {}
    scheduleSaveLibraryToDisk();
    updateLikedBadge();
    updateNowPlayingLikeBtn();
  }

  function savePlaylists() {
    try {
      localStorage.setItem(STORAGE_KEYS.PLAYLISTS, JSON.stringify(state.playlists));
    } catch (e) {}
    scheduleSaveLibraryToDisk();
    renderPlaylistsSidebar();
  }

  function updateLikedBadge() {
    if (elements.likedBadge) {
      elements.likedBadge.textContent = state.likedSongs.length;
    }
  }

  function isTrackLiked(trackId) {
    if (!trackId) return false;
    return state.likedSongs.some(t => t.id === trackId);
  }

  function toggleLikeTrack(track) {
    if (!track || !track.id) return;
    const idx = state.likedSongs.findIndex(t => t.id === track.id);
    if (idx >= 0) {
      state.likedSongs.splice(idx, 1);
    } else {
      // Ensure full track metadata is preserved
      state.likedSongs.unshift({
        id: track.id,
        source: track.source || 'youtube',
        title: track.title || 'Unknown Title',
        artist: track.artist || 'Unknown Artist',
        duration: track.duration || '--:--',
        thumbnail: track.thumbnail || ''
      });
    }
    saveLikedSongs();

    if (state.activeTab === 'liked') {
      renderTrackList(state.likedSongs, false, true);
      elements.viewSubtitle.textContent = `${state.likedSongs.length} liked track(s) • Auto-saved`;
    } else {
      updateTrackRowLikeVisuals(track.id);
    }
  }

  function updateTrackRowLikeVisuals(trackId) {
    const rows = elements.trackListContainer.querySelectorAll(`.track-row[data-id="${trackId}"]`);
    const liked = isTrackLiked(trackId);
    rows.forEach(r => {
      const btn = r.querySelector('.like-btn');
      if (btn) {
        btn.classList.toggle('liked', liked);
        btn.title = liked ? 'Unlike' : 'Like';
        const svg = btn.querySelector('svg');
        if (svg) svg.setAttribute('fill', liked ? 'currentColor' : 'none');
      }
    });
  }

  function updateNowPlayingLikeBtn() {
    if (!elements.nowPlayingLikeBtn) return;
    if (!state.currentTrack) {
      elements.nowPlayingLikeBtn.classList.remove('liked');
      const svg = elements.nowPlayingLikeBtn.querySelector('svg');
      if (svg) svg.setAttribute('fill', 'none');
      return;
    }
    const liked = isTrackLiked(state.currentTrack.id);
    elements.nowPlayingLikeBtn.classList.toggle('liked', liked);
    elements.nowPlayingLikeBtn.title = liked ? 'Unlike track' : 'Like track';
    const svg = elements.nowPlayingLikeBtn.querySelector('svg');
    if (svg) svg.setAttribute('fill', liked ? 'currentColor' : 'none');
  }

  // Custom Playlists Operations
  function createPlaylist(name) {
    if (!name || !name.trim()) return null;
    const pl = {
      id: 'pl_' + Date.now(),
      name: name.trim(),
      createdAt: Date.now(),
      tracks: []
    };
    state.playlists.push(pl);
    savePlaylists();
    return pl;
  }

  function deletePlaylist(playlistId) {
    state.playlists = state.playlists.filter(p => p.id !== playlistId);
    savePlaylists();
    if (state.activeTab === playlistId) {
      switchTab('discover');
    }
  }

  function addTrackToPlaylist(playlistId, track) {
    const pl = state.playlists.find(p => p.id === playlistId);
    if (!pl) return;
    if (!pl.tracks.some(t => t.id === track.id)) {
      pl.tracks.push({
        id: track.id,
        source: track.source || 'youtube',
        title: track.title || 'Unknown Title',
        artist: track.artist || 'Unknown Artist',
        duration: track.duration || '--:--',
        thumbnail: track.thumbnail || ''
      });
      savePlaylists();
    }
  }

  function removeTrackFromPlaylist(playlistId, trackId) {
    const pl = state.playlists.find(p => p.id === playlistId);
    if (!pl) return;
    pl.tracks = pl.tracks.filter(t => t.id !== trackId);
    savePlaylists();
    if (state.activeTab === playlistId) {
      renderTrackList(pl.tracks, false, false, pl.id);
      elements.viewSubtitle.textContent = `${pl.tracks.length} track(s) • Custom Playlist`;
    }
  }

  function toggleTrackInPlaylist(playlistId, track) {
    const pl = state.playlists.find(p => p.id === playlistId);
    if (!pl) return false;
    const exists = pl.tracks.some(t => t.id === track.id);
    if (exists) {
      removeTrackFromPlaylist(playlistId, track.id);
      return false;
    } else {
      addTrackToPlaylist(playlistId, track);
      return true;
    }
  }

  function renderPlaylistsSidebar() {
    if (!elements.playlistsList) return;
    elements.playlistsList.innerHTML = '';

    if (state.playlists.length === 0) {
      elements.playlistsList.innerHTML = `
        <div style="font-size: 0.74rem; color: var(--text-dim); padding: 6px 10px; font-style: italic;">
          No playlists yet. Click + above to create one.
        </div>
      `;
      return;
    }

    state.playlists.forEach(pl => {
      const item = document.createElement('div');
      item.className = `playlist-nav-item ${state.activeTab === pl.id ? 'active' : ''}`;
      item.setAttribute('data-playlist-id', pl.id);

      item.innerHTML = `
        <svg class="playlist-nav-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="8" y1="6" x2="21" y2="6"></line>
          <line x1="8" y1="12" x2="21" y2="12"></line>
          <line x1="8" y1="18" x2="21" y2="18"></line>
          <line x1="3" y1="6" x2="3.01" y2="6"></line>
          <line x1="3" y1="12" x2="3.01" y2="12"></line>
          <line x1="3" y1="18" x2="3.01" y2="18"></line>
        </svg>
        <span class="playlist-name-text" title="${pl.name}">${pl.name}</span>
        <span class="playlist-track-badge">${pl.tracks ? pl.tracks.length : 0}</span>
        <button class="playlist-delete-icon-btn" title="Delete Playlist">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      `;

      item.addEventListener('click', (e) => {
        if (e.target.closest('.playlist-delete-icon-btn')) {
          e.stopPropagation();
          if (confirm(`Delete playlist "${pl.name}"?`)) {
            deletePlaylist(pl.id);
          }
          return;
        }
        switchTab(pl.id);
      });

      elements.playlistsList.appendChild(item);
    });
  }

  // Format seconds to mm:ss
  function formatTime(seconds) {
    if (!seconds || isNaN(seconds) || seconds < 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  }

  // Set active search source
  function setSource(source) {
    if (state.activeSource === source) return;
    state.activeSource = source;
    state.activeCategory = 'all';
    state.discoverData = null;

    if (source === 'youtube') {
      elements.sourceBtnYouTube.classList.add('active');
      elements.sourceBtnSpotify.classList.remove('active');
      elements.searchInput.placeholder = 'Search YouTube songs, artists, or paste link...';
    } else {
      elements.sourceBtnSpotify.classList.add('active');
      elements.sourceBtnYouTube.classList.remove('active');
      elements.searchInput.placeholder = 'Search Spotify songs, artists, or paste link...';
    }

    // Refresh smart queue when source switches so next song recommendation matches active mode
    smartAutoplayQueue = [];
    preloadedTrack = null;
    isStandbyReady = false;
    replenishSmartQueue(true);

    const query = elements.searchInput.value.trim();
    if (query) {
      executeSearch(query);
    } else {
      if (state.activeTab !== 'discover') {
        switchTab('discover');
      } else {
        loadPopularTracks();
      }
    }
  }

  // Switch View Tab (Discover vs Queue vs Liked vs Custom Playlist)
  function switchTab(tab) {
    state.activeTab = tab;

    // Update active state across standard nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      if (item.dataset.tab === tab) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Update active state across custom playlist items
    document.querySelectorAll('.playlist-nav-item').forEach(item => {
      if (item.getAttribute('data-playlist-id') === tab) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Reset action buttons visibility
    elements.clearQueueBtn.style.display = 'none';
    elements.playlistPlayAllBtn.style.display = 'none';
    elements.deletePlaylistBtn.style.display = 'none';

    if (tab === 'discover') {
      if (elements.categoryPillBar) elements.categoryPillBar.style.display = 'flex';
      const sourceLabel = state.activeSource === 'youtube' ? 'YouTube Discovery' : 'Spotify Discovery';
      elements.viewTitle.textContent = sourceLabel;
      elements.viewSubtitle.textContent = state.activeSource === 'youtube'
        ? 'Hip-hop, trap, rap & street anthems'
        : 'Pop, R&B & mainstream chart hits';
      const currentSource = (state.currentList && state.currentList[0]) ? state.currentList[0].source : null;
      if (!state.discoverData || currentSource !== state.activeSource) {
        loadPopularTracks();
      } else {
        renderCategoryPills();
        renderDiscoverContent();
      }
    } else {
      if (elements.categoryPillBar) elements.categoryPillBar.style.display = 'none';
      if (tab === 'queue') {
        elements.viewTitle.textContent = 'Current Queue';
        elements.viewSubtitle.textContent = `${state.queue.length} track(s) in queue`;
        elements.clearQueueBtn.style.display = state.queue.length > 0 ? 'inline-block' : 'none';
        renderTrackList(state.queue, true);
      } else if (tab === 'liked') {
        elements.viewTitle.textContent = 'Liked Songs';
        elements.viewSubtitle.textContent = `${state.likedSongs.length} track(s) • Auto-saved`;
        elements.playlistPlayAllBtn.style.display = state.likedSongs.length > 0 ? 'inline-flex' : 'none';
        renderTrackList(state.likedSongs, false, true);
      } else if (tab.startsWith('pl_')) {
        const pl = state.playlists.find(p => p.id === tab);
        if (!pl) {
          switchTab('discover');
          return;
        }
        elements.viewTitle.textContent = pl.name;
        elements.viewSubtitle.textContent = `${pl.tracks.length} track(s) • Custom Playlist`;
        elements.playlistPlayAllBtn.style.display = pl.tracks.length > 0 ? 'inline-flex' : 'none';
        elements.deletePlaylistBtn.style.display = 'inline-block';
        renderTrackList(pl.tracks, false, false, pl.id);
      }
    }
  }

  // Render Tracks to UI
  function renderTrackList(tracks, isQueueView = false, isLikedView = false, playlistId = null, targetContainer = null) {
    const container = targetContainer || elements.trackListContainer;
    if (!targetContainer) {
      container.innerHTML = '';
    }

    if (!tracks || tracks.length === 0) {
      let emptyMsg = 'No tracks found. Try searching for a song or artist above.';
      if (isQueueView) emptyMsg = 'Your queue is empty. Click + on any track to add it here.';
      else if (isLikedView) emptyMsg = 'No liked songs yet. Click the heart icon on any track to add it here!';
      else if (playlistId) emptyMsg = 'This playlist is empty. Search for songs and click the playlist icon to add them.';

      container.innerHTML = `
        <div style="text-align: center; padding: 60px 0; color: var(--text-dim); font-size: 0.95rem;">
          ${emptyMsg}
        </div>
      `;
      return;
    }

    tracks.forEach((track, index) => {
      const isCurrent = state.currentTrack && state.currentTrack.id === track.id;
      const row = document.createElement('div');
      row.className = `track-row ${isCurrent ? 'now-playing' : ''}`;
      row.setAttribute('data-id', track.id);

      const sourceBadgeClass = track.source === 'spotify' ? 'badge-spotify' : 'badge-youtube';
      const sourceLabel = track.source === 'spotify' ? 'SPOTIFY' : 'YOUTUBE';
      const liked = isTrackLiked(track.id);

      row.innerHTML = `
        <div class="track-thumb-box">
          <img src="${track.thumbnail || 'https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=100&q=80'}" alt="Thumb" loading="lazy">
          <div class="play-overlay" title="Play Now">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>
          </div>
        </div>
        <div class="track-info-col">
          <div class="track-title-text" title="${track.title}">${track.title}</div>
          <div class="track-artist-text">${track.artist}</div>
        </div>
        <div>
          <span class="track-source-badge ${sourceBadgeClass}">${sourceLabel}</span>
        </div>
        <div class="track-duration-text">${track.duration || '--:--'}</div>
        <div class="track-actions">
          <button class="track-action-btn like-btn ${liked ? 'liked' : ''}" title="${liked ? 'Unlike' : 'Like'}">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="${liked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
              <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
            </svg>
          </button>
          <button class="track-action-btn add-playlist-btn" title="Add to Playlist">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 12H3M16 6H3M16 18H3M18 9v6M15 12h6"/>
            </svg>
          </button>
          <button class="track-action-btn add-queue-btn" title="Add to Queue">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>
          ${playlistId ? `
          <button class="track-action-btn remove-track-btn" title="Remove from this playlist">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
          ` : ''}
        </div>
      `;

      // Proactive stream pre-warming on hover for instant playback on click
      row.addEventListener('mouseenter', () => {
        if (track.id && !deadTracksSet.has(track.id) && !track.unplayable) {
          fetch(`/api/preload?id=${encodeURIComponent(track.id)}&title=${encodeURIComponent(track.title || '')}&artist=${encodeURIComponent(track.artist || '')}`).catch(() => {});
          // If idle, buffer candidate into standby deck so user click is 100% instant!
          if (!state.isPlaying && !state.currentTrack) {
            preloadNextTrack(track);
          }
        }
      });

      // Entire row is clickable to play immediately
      row.addEventListener('click', (e) => {
        if (e.target.closest('.track-action-btn')) return;
        playTrackImmediately(track);
      });

      // Like Button
      const likeBtn = row.querySelector('.like-btn');
      likeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleLikeTrack(track);
      });

      // Add to Playlist Button
      const addPlaylistBtn = row.querySelector('.add-playlist-btn');
      addPlaylistBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openAddToPlaylistModal(track);
      });

      // Add to Queue Button
      const addQueueBtn = row.querySelector('.add-queue-btn');
      addQueueBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        addToQueue(track);
      });

      // Remove from Playlist Button (if in a custom playlist)
      if (playlistId) {
        const removeBtn = row.querySelector('.remove-track-btn');
        if (removeBtn) {
          removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeTrackFromPlaylist(playlistId, track.id);
          });
        }
      }

      container.appendChild(row);
    });

    // Proactively pre-warm top 2 tracks in the newly rendered list for instant zero-delay playback
    if (!targetContainer && tracks && tracks.length > 0) {
      for (const t of tracks.slice(0, 2)) {
        if (t && t.id) {
          fetch(`/api/preload?id=${encodeURIComponent(t.id)}&title=${encodeURIComponent(t.title || '')}&artist=${encodeURIComponent(t.artist || '')}`).catch(() => {});
        }
      }
    }
  }

  // Category Icon Resolver
  function getCategoryIcon(catId) {
    const icons = {
      for_you: '✨',
      all: '🔥',
      rap_trap: '⚡',
      drill_underground: '🎤',
      chill_lofi: '🌙',
      rock_alt: '🎸',
      viral_remix: '🔥',
      pop_hits: '🌟',
      hiphop_central: '💎',
      rnb_soul: '🔮',
      latin_fire: '🌴',
      edm_dance: '⚡'
    };
    return icons[catId] || '🎵';
  }

  // Batch Play All Songs In A Category
  function playCategoryBatch(tracks, catName) {
    if (!tracks || tracks.length === 0) return;
    state.queue = tracks.slice(1).map(t => ({ ...t }));
    updateQueueUI();
    playTrackImmediately(tracks[0]);
  }

  // Render Horizontal Category Filter Pills
  function renderCategoryPills() {
    if (!elements.categoryPillBar) return;
    if (state.activeTab !== 'discover') {
      elements.categoryPillBar.style.display = 'none';
      return;
    }
    elements.categoryPillBar.style.display = 'flex';
    elements.categoryPillBar.innerHTML = '';

    if (!state.discoverData || !state.discoverData.categories) return;

    // 1. "All Categories" pill
    const allPill = document.createElement('button');
    allPill.className = `category-pill ${state.activeCategory === 'all' ? 'active' : ''}`;
    allPill.dataset.catId = 'all';
    let totalTracks = 0;
    Object.values(state.discoverData.categories).forEach(c => {
      totalTracks += (c.tracks ? c.tracks.length : 0);
    });
    allPill.innerHTML = `<span>🔥 All Categories</span><span class="pill-badge">${totalTracks}</span>`;
    allPill.addEventListener('click', () => {
      state.activeCategory = 'all';
      updateActivePillClass();
      renderDiscoverContent();
    });
    elements.categoryPillBar.appendChild(allPill);

    // 2. "Made For You" pill (if available)
    if (state.discoverData.for_you && state.discoverData.for_you.length > 0) {
      const forYouPill = document.createElement('button');
      forYouPill.className = `category-pill ${state.activeCategory === 'for_you' ? 'active' : ''}`;
      forYouPill.dataset.catId = 'for_you';
      forYouPill.innerHTML = `<span>✨ Made For You</span><span class="pill-badge">${state.discoverData.for_you.length}</span>`;
      forYouPill.addEventListener('click', () => {
        state.activeCategory = 'for_you';
        updateActivePillClass();
        renderDiscoverContent();
      });
      elements.categoryPillBar.appendChild(forYouPill);
    }

    // 3. Platform Category Pills (25 tracks each)
    Object.entries(state.discoverData.categories).forEach(([catId, catInfo]) => {
      const pill = document.createElement('button');
      pill.className = `category-pill ${state.activeCategory === catId ? 'active' : ''}`;
      pill.dataset.catId = catId;
      const icon = getCategoryIcon(catId);
      const count = (catInfo.tracks && catInfo.tracks.length) || 0;
      pill.innerHTML = `<span>${icon} ${catInfo.name}</span><span class="pill-badge">${count}</span>`;
      pill.addEventListener('click', () => {
        state.activeCategory = catId;
        updateActivePillClass();
        renderDiscoverContent();
      });
      elements.categoryPillBar.appendChild(pill);
    });
  }

  function updateActivePillClass() {
    if (!elements.categoryPillBar) return;
    elements.categoryPillBar.querySelectorAll('.category-pill').forEach(pill => {
      if (pill.dataset.catId === state.activeCategory) {
        pill.classList.add('active');
      } else {
        pill.classList.remove('active');
      }
    });
  }

  // Render Categorized Sections or Single Category View
  function renderDiscoverContent() {
    if (!state.discoverData) return;
    elements.trackListContainer.innerHTML = '';

    const sourceName = state.activeSource === 'spotify' ? 'Spotify' : 'YouTube';

    if (state.activeCategory === 'all') {
      elements.viewTitle.textContent = `${sourceName} Discovery`;
      elements.viewSubtitle.textContent = state.activeSource === 'youtube'
        ? '5 Curated Categories • 25 Tracks Each + Personalized Picks'
        : '5 Chart Categories • 25 Tracks Each + Personalized Picks';

      // Section 1: Made For You
      if (state.discoverData.for_you && state.discoverData.for_you.length > 0) {
        const forYouHeader = document.createElement('div');
        forYouHeader.className = 'category-section-header';
        forYouHeader.innerHTML = `
          <div class="category-section-title">
            <span class="cat-icon">✨</span>
            <span>Made For You</span>
            <span class="category-section-count">${state.discoverData.for_you.length} TRACKS</span>
          </div>
          <div style="display:flex; align-items:center; gap:12px;">
            <span style="font-size: 0.8rem; color: var(--text-dim);">${state.discoverData.for_you_reason || 'Similar to songs you listen to'}</span>
            <button class="category-play-btn" id="playMixBtn">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>
              Play Mix
            </button>
          </div>
        `;
        elements.trackListContainer.appendChild(forYouHeader);
        forYouHeader.querySelector('#playMixBtn').addEventListener('click', () => {
          playCategoryBatch(state.discoverData.for_you, 'Made For You');
        });

        const forYouBox = document.createElement('div');
        forYouBox.className = 'category-track-group';
        elements.trackListContainer.appendChild(forYouBox);
        renderTrackList(state.discoverData.for_you, false, false, null, forYouBox);
      }

      // Section 2..6: Each of the 5 categories
      if (state.discoverData.categories) {
        Object.entries(state.discoverData.categories).forEach(([catId, catInfo]) => {
          const catHeader = document.createElement('div');
          catHeader.className = 'category-section-header';
          const icon = getCategoryIcon(catId);
          const count = catInfo.tracks ? catInfo.tracks.length : 0;
          catHeader.innerHTML = `
            <div class="category-section-title">
              <span class="cat-icon">${icon}</span>
              <span>${catInfo.name}</span>
              <span class="category-section-count">${count} TRACKS</span>
            </div>
            <button class="category-play-btn">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>
              Play Category
            </button>
          `;
          elements.trackListContainer.appendChild(catHeader);
          catHeader.querySelector('.category-play-btn').addEventListener('click', () => {
            playCategoryBatch(catInfo.tracks, catInfo.name);
          });

          const catBox = document.createElement('div');
          catBox.className = 'category-track-group';
          elements.trackListContainer.appendChild(catBox);
          renderTrackList(catInfo.tracks, false, false, null, catBox);
        });
      }
      return;
    }

    if (state.activeCategory === 'for_you') {
      elements.viewTitle.textContent = '✨ Made For You';
      elements.viewSubtitle.textContent = state.discoverData.for_you_reason || 'Similar to songs you listen to';

      const forYouHeader = document.createElement('div');
      forYouHeader.className = 'category-section-header';
      forYouHeader.style.marginTop = '0px';
      forYouHeader.innerHTML = `
        <div class="category-section-title">
          <span class="cat-icon">✨</span>
          <span>Personalized Mix</span>
          <span class="category-section-count">${state.discoverData.for_you ? state.discoverData.for_you.length : 0} TRACKS</span>
        </div>
        <button class="category-play-btn" id="playMixBtnSingle">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>
          Play Mix
        </button>
      `;
      elements.trackListContainer.appendChild(forYouHeader);
      forYouHeader.querySelector('#playMixBtnSingle').addEventListener('click', () => {
        playCategoryBatch(state.discoverData.for_you, 'Made For You');
      });

      renderTrackList(state.discoverData.for_you || [], false, false, null, elements.trackListContainer);
      return;
    }

    // Specific category
    const cat = state.discoverData.categories ? state.discoverData.categories[state.activeCategory] : null;
    if (cat) {
      const icon = getCategoryIcon(state.activeCategory);
      elements.viewTitle.textContent = `${icon} ${cat.name}`;
      elements.viewSubtitle.textContent = cat.description || `${cat.tracks ? cat.tracks.length : 25} hand-picked tracks`;

      const catHeader = document.createElement('div');
      catHeader.className = 'category-section-header';
      catHeader.style.marginTop = '0px';
      catHeader.innerHTML = `
        <div class="category-section-title">
          <span class="cat-icon">${icon}</span>
          <span>${cat.name}</span>
          <span class="category-section-count">${cat.tracks ? cat.tracks.length : 0} TRACKS</span>
        </div>
        <button class="category-play-btn" id="playCatBtnSingle">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>
          Play Category
        </button>
      `;
      elements.trackListContainer.appendChild(catHeader);
      catHeader.querySelector('#playCatBtnSingle').addEventListener('click', () => {
        playCategoryBatch(cat.tracks, cat.name);
      });

      renderTrackList(cat.tracks || [], false, false, null, elements.trackListContainer);
    }
  }

  // Load Discover Categories and For You Mix
  async function loadPopularTracks() {
    showLoader(true, 'Loading discover categories...');
    try {
      const sourceLabel = state.activeSource === 'youtube' ? 'YouTube Discovery' : 'Spotify Discovery';
      elements.viewTitle.textContent = sourceLabel;
      elements.viewSubtitle.textContent = state.activeSource === 'youtube'
        ? 'Hip-hop, trap, rap & street anthems'
        : 'Pop, R&B & mainstream chart hits';

      const res = await fetch(`/api/discover?source=${state.activeSource}`);
      const data = await res.json();
      state.discoverData = data;

      // Flatten tracks into state.currentList for autoplay / indexing
      let allTracks = [];
      if (data.for_you && Array.isArray(data.for_you)) {
        allTracks.push(...data.for_you);
      }
      if (data.categories) {
        Object.values(data.categories).forEach(cat => {
          if (cat.tracks && Array.isArray(cat.tracks)) {
            allTracks.push(...cat.tracks);
          }
        });
      }
      state.currentList = allTracks;

      if (data.dead_tracks && Array.isArray(data.dead_tracks)) {
        const featuredIds = new Set(allTracks.map(t => t.id));
        data.dead_tracks.forEach(id => {
          if (!featuredIds.has(id)) {
            deadTracksSet.add(id);
          }
        });
      }

      renderCategoryPills();
      renderDiscoverContent();

      // Pre-buffer top tracks into standbyDeck for instant playback!
      if (state.currentList.length > 0 && !state.isPlaying && !state.currentTrack) {
        preloadNextTrack(state.currentList[0]);
        for (const t of state.currentList.slice(1, 3)) {
          if (t && t.id) fetch(`/api/preload?id=${encodeURIComponent(t.id)}&title=${encodeURIComponent(t.title||'')}&artist=${encodeURIComponent(t.artist||'')}`).catch(()=>{});
        }
      }
    } catch (e) {
      console.error('Failed to load discover categories:', e);
      renderTrackList([]);
    } finally {
      showLoader(false);
    }
  }

  // Execute Search
  async function executeSearch(query) {
    if (!query.trim()) {
      if (elements.categoryPillBar && state.activeTab === 'discover') {
        elements.categoryPillBar.style.display = 'flex';
      }
      loadPopularTracks();
      return;
    }

    if (elements.categoryPillBar) {
      elements.categoryPillBar.style.display = 'none';
    }

    showLoader(true, `Searching ${state.activeSource.toUpperCase()} for "${query}"...`);
    elements.viewTitle.textContent = `Search: "${query}"`;
    elements.viewSubtitle.textContent = `Streaming via ${state.activeSource.toUpperCase()}`;

    try {
      const encoded = encodeURIComponent(query);
      const res = await fetch(`/api/search?q=${encoded}&source=${state.activeSource}`);
      const data = await res.json();
      state.currentList = data.tracks || [];
      renderTrackList(state.currentList);
    } catch (err) {
      console.error('Search error:', err);
      renderTrackList([]);
    } finally {
      showLoader(false);
    }
  }

  function showLoader(visible, msg = 'Loading...') {
    elements.loaderText.textContent = msg;
    elements.loader.style.display = visible ? 'flex' : 'none';
    if (visible) elements.trackListContainer.style.display = 'none';
    else elements.trackListContainer.style.display = 'flex';
  }

  // Queue Operations
  function addToQueue(track) {
    state.queue.push(track);
    updateQueueUI();
  }

  function updateQueueUI() {
    elements.queueBadge.textContent = state.queue.length;
    if (state.activeTab === 'queue') {
      renderTrackList(state.queue, true);
    }
  }

  function clearQueue() {
    state.queue = [];
    state.currentIndex = -1;
    updateQueueUI();
  }

  // ============================================================
  // NATIVE AUDIO STREAMING ENGINE
  // ============================================================
  // Smart Autoplay & Continuous Radio Recommendation Buffer
  // ============================================================
  let smartAutoplayQueue = [];
  let isFetchingRecommendation = false;
  let currentTrackLogged = false;
  let recentPlayedIds = [];
  let recentPlayedTitleKeys = new Set();
  let playbackWatchdogTimer = null;
  let lastAudioPosition = 0;
  let stallCounter = 0;

  // Canonical song title key extractor for duplicate prevention
  function getSongTitleKey(title, artist = '') {
    if (!title) return '';
    let t = title.toLowerCase();
    t = t.replace(/[\(\[][^\)\]]*[\)\]]/g, '');
    t = t.replace(/\b(?:feat\.?|ft\.?|featuring)\b.*$/g, '');
    t = t.replace(/\s*-\s*topic\b/g, '');
    t = t.replace(/\bvevo\b/g, '');

    const artistCompact = (artist || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    let fullComp = t.replace(/[^a-z0-9]/g, '');

    if (t.includes(' - ')) {
      const parts = t.split(' - ');
      const p1Comp = parts[0].replace(/[^a-z0-9]/g, '');
      const p2Comp = parts[1].replace(/[^a-z0-9]/g, '');
      if (artistCompact && p1Comp.includes(artistCompact)) return p2Comp;
      if (artistCompact && p2Comp.includes(artistCompact)) return p1Comp;
      return p2Comp || fullComp;
    }

    if (artistCompact && fullComp.startsWith(artistCompact)) {
      fullComp = fullComp.slice(artistCompact.length);
    }
    return fullComp;
  }

  function isDuplicateSongTitle(candTitle, candArtist, referenceKeys) {
    const key = getSongTitleKey(candTitle, candArtist);
    if (!key || key.length < 3) return false;
    for (const ref of referenceKeys) {
      if (!ref || ref.length < 3) continue;
      if (key === ref) return true;
      if (key.length >= 5 && ref.length >= 5) {
        if (key.includes(ref) || ref.includes(key)) return true;
      }
    }
    return false;
  }

  // Active deck accessor
  function getActiveDeck() {
    return currentDeck;
  }

  // Pre-buffer upcoming track audio bytes on standbyDeck in background while current song plays
  function preloadNextTrack(track) {
    if (!track || !track.id) return;
    if (deadTracksSet.has(track.id) || track.unplayable) {
      console.warn(`[Preloader] Skipping unplayable track: ${track.title} (${track.id})`);
      ensureNextTrackPreloaded();
      return;
    }
    if (preloadedTrack && preloadedTrack.id === track.id && isStandbyReady) return;

    preloadedTrack = track;
    isStandbyReady = false;

    standbyDeck.oncanplay = () => {
      console.log(`[Preloader] Verified playable & ready on standby deck: ${track.title}`);
      isStandbyReady = true;
    };

    standbyDeck.onerror = (e) => {
      console.warn(`[Preloader] Standby track unplayable: ${track.title} (${track.id}). Quarantining.`);
      isStandbyReady = false;
      preloadedTrack = null;
      deadTracksSet.add(track.id);
      track.unplayable = true;

      fetch(`/api/dead_track?id=${encodeURIComponent(track.id)}`).catch(() => {});

      if (smartAutoplayQueue.length > 0 && smartAutoplayQueue[0].id === track.id) {
        smartAutoplayQueue.shift();
      }
      if (state.queue.length > 0 && state.queue[0].id === track.id) {
        state.queue.shift();
        updateQueueUI();
      }

      ensureNextTrackPreloaded();
    };

    // 1. Warm up backend cache so stream URL is ready in 0ms
    fetch(`/api/preload?id=${encodeURIComponent(track.id)}&title=${encodeURIComponent(track.title || '')}&artist=${encodeURIComponent(track.artist || '')}`).catch(() => {});

    // 2. Load into standby deck so browser pre-buffers audio chunks in memory
    const streamUrl = `/api/stream?id=${encodeURIComponent(track.id)}&title=${encodeURIComponent(track.title || '')}&artist=${encodeURIComponent(track.artist || '')}`;
    standbyDeck.src = streamUrl;
    standbyDeck.preload = 'auto';
    standbyDeck.volume = sliderToPerceptualVolume(state.volume);
    standbyDeck.load();
    console.log(`[Preloader] Pre-buffering candidate into standby deck: ${track.title}`);
  }

  // Determine what the upcoming song is and ensure it is preloaded
  function ensureNextTrackPreloaded() {
    if (preloadedTrack && isStandbyReady) return;

    let upcoming = null;
    // 1. Manual user queue
    while (state.queue.length > 0) {
      const cand = state.queue[0];
      if (cand.unplayable || deadTracksSet.has(cand.id)) {
        state.queue.shift();
        updateQueueUI();
      } else {
        upcoming = cand;
        break;
      }
    }

    // 2. Custom playlist / Liked Songs
    if (!upcoming && state.activeTab !== 'discover' && state.activeTab !== 'queue' && state.currentList.length > 0) {
      const curIdx = state.currentList.findIndex(t => t.id === state.currentTrack?.id);
      if (curIdx !== -1) {
        for (let i = curIdx + 1; i < state.currentList.length; i++) {
          const cand = state.currentList[i];
          if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
            upcoming = cand;
            break;
          }
        }
      }
    }

    // 3. Smart Autoplay Queue
    if (!upcoming) {
      const currentKey = state.currentTrack ? getSongTitleKey(state.currentTrack.title, state.currentTrack.artist) : '';
      while (smartAutoplayQueue.length > 0) {
        const cand = smartAutoplayQueue[0];
        if (cand.unplayable || deadTracksSet.has(cand.id) || (currentKey && isDuplicateSongTitle(cand.title, cand.artist, [currentKey]))) {
          smartAutoplayQueue.shift();
        } else {
          upcoming = cand;
          break;
        }
      }
    }

    if (upcoming) {
      preloadNextTrack(upcoming);
    } else {
      replenishSmartQueue().then(() => {
        if (!preloadedTrack && smartAutoplayQueue.length > 0) {
          preloadNextTrack(smartAutoplayQueue[0]);
        }
      });
    }
  }

  // Record track play to history & taste profile engine
  function logTrackPlay(track) {
    if (!track || !track.id) return;
    try {
      fetch('/api/history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: track.id,
          title: track.title,
          artist: track.artist,
          source: track.source || 'youtube'
        })
      }).catch(() => {});
    } catch (_) {}
  }

  // Continuously replenish smart autoplay queue in the background (6-10 tracks ready)
  async function replenishSmartQueue(force = false) {
    if (isFetchingRecommendation) return;
    if (!force && smartAutoplayQueue.length >= 6) return;
    isFetchingRecommendation = true;

    try {
      const cur = state.currentTrack;
      const exclude = Array.from(new Set([
        ...recentPlayedIds,
        ...(cur ? [cur.id] : []),
        ...smartAutoplayQueue.map(t => t.id)
      ])).join(',');

      const params = new URLSearchParams({
        seed_id: cur ? cur.id : '',
        seed_title: cur ? cur.title : '',
        seed_artist: cur ? cur.artist : '',
        source: state.activeSource || (cur ? cur.source : 'youtube'),
        exclude_ids: exclude
      });

      const res = await fetch(`/api/recommendations?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        const recs = data.recommendations || [];
        if (recs.length > 0) {
          const existingIds = new Set(smartAutoplayQueue.map(t => t.id));
          const currentKey = state.currentTrack ? getSongTitleKey(state.currentTrack.title, state.currentTrack.artist) : '';
          const activeKeys = new Set([...recentPlayedTitleKeys, ...(currentKey ? [currentKey] : [])]);

          for (const r of recs) {
            if (existingIds.has(r.id) || recentPlayedIds.includes(r.id)) continue;
            if (isDuplicateSongTitle(r.title, r.artist, activeKeys)) {
              console.log(`[SmartQueue] Filtered duplicate upload of song: ${r.title}`);
              continue;
            }
            existingIds.add(r.id);
            const rKey = getSongTitleKey(r.title, r.artist);
            if (rKey) activeKeys.add(rKey);
            smartAutoplayQueue.push(r);
          }
          // As soon as candidates are in queue, preload the first one!
          ensureNextTrackPreloaded();
        }
      }
    } catch (e) {
      console.warn('Smart queue replenishment error:', e);
    } finally {
      isFetchingRecommendation = false;
    }
  }

  // Instant zero-delay deck swap
  function executeDeckSwapAndPlay(track) {
    currentDeck.pause();
    currentDeck.src = '';
    currentDeck.oncanplay = null;
    currentDeck.onerror = null;

    // Instant swap: standby becomes active
    const oldDeck = currentDeck;
    currentDeck = standbyDeck;
    standbyDeck = oldDeck;

    // Clear standby ready flag & preloaded reference
    preloadedTrack = null;
    isStandbyReady = false;

    state.currentTrack = track;
    currentTrackLogged = false;
    stallCounter = 0;
    lastAudioPosition = 0;
    if (track.id) {
      recentPlayedIds = [track.id, ...recentPlayedIds.filter(id => id !== track.id)].slice(0, 50);
    }
    if (track.title) {
      const songKey = getSongTitleKey(track.title, track.artist);
      if (songKey) recentPlayedTitleKeys.add(songKey);
    }

    updateNowPlayingMeta(track);
    elements.pipelineStatus.textContent = track.reason ? `✨ ${track.reason}` : (track.source === 'spotify' ? 'Spotify Direct' : 'YouTube Direct');
    elements.engineBadge.textContent = 'Streaming';
    currentDeck.volume = sliderToPerceptualVolume(state.volume);

    // Play immediately without buffering pause (audio chunks already in memory!)
    currentDeck.play().then(() => {
      state.isPlaying = true;
      updatePlayPauseButton();
      elements.equalizerVisualizer.style.display = 'flex';
      // Immediately start preloading the following song on the newly available standbyDeck!
      ensureNextTrackPreloaded();
    }).catch(err => {
      console.warn('Instant deck play error:', err);
      handleDeckPlaybackError(track);
    });

    updateMediaSession(track);
  }

  // Gracefully handles deck playback error without rapid skips or freezing
  function handleDeckPlaybackError(track) {
    if (!track) return;
    console.warn(`[Deck] Playback error on track: ${track.title} (${track.id}). Quarantining.`);
    deadTracksSet.add(track.id);
    track.unplayable = true;
    fetch(`/api/dead_track?id=${encodeURIComponent(track.id)}`).catch(() => {});

    elements.pipelineStatus.textContent = '✨ Finding next playable song...';

    // If preloadedTrack on standbyDeck is verified playable, swap immediately!
    if (preloadedTrack && isStandbyReady && !preloadedTrack.unplayable && !deadTracksSet.has(preloadedTrack.id)) {
      const next = preloadedTrack;
      executeDeckSwapAndPlay(next);
      return;
    }

    findAndPlayNextPlayableTrack();
  }

  // Finds next verified playable candidate and transitions cleanly without skipping
  async function findAndPlayNextPlayableTrack() {
    elements.pipelineStatus.textContent = '✨ Finding playable track...';

    // 1. Consume from smart queue
    while (smartAutoplayQueue.length > 0) {
      const cand = smartAutoplayQueue.shift();
      if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
        playTrackImmediately(cand);
        replenishSmartQueue();
        return;
      }
    }

    // 2. Fetch fresh recommendations
    await replenishSmartQueue(true);
    while (smartAutoplayQueue.length > 0) {
      const cand = smartAutoplayQueue.shift();
      if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
        playTrackImmediately(cand);
        replenishSmartQueue();
        return;
      }
    }

    // 3. Fallback to Liked Songs
    for (const cand of state.likedSongs) {
      if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
        cand.reason = 'From your Liked Songs';
        playTrackImmediately(cand);
        replenishSmartQueue();
        return;
      }
    }

    // 4. Fallback to current list
    for (const cand of state.currentList) {
      if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
        playTrackImmediately(cand);
        replenishSmartQueue();
        return;
      }
    }
  }

  // Autonomous Smart Autoplay Trigger (Instantaneous 0ms switch + non-stop playback)
  async function triggerSmartAutoplay() {
    // 1. Consume from preloaded smart buffer if ready (0ms gapless transition!)
    if (preloadedTrack && isStandbyReady && !preloadedTrack.unplayable && !deadTracksSet.has(preloadedTrack.id)) {
      const next = preloadedTrack;
      if (smartAutoplayQueue.length > 0 && smartAutoplayQueue[0].id === next.id) {
        smartAutoplayQueue.shift();
      }
      executeDeckSwapAndPlay(next);
      return;
    }

    while (smartAutoplayQueue.length > 0) {
      const next = smartAutoplayQueue.shift();
      if (!next.unplayable && !deadTracksSet.has(next.id)) {
        playTrackImmediately(next);
        replenishSmartQueue();
        return;
      }
    }

    // 2. If queue is dry, fetch on-the-fly
    elements.pipelineStatus.textContent = '✨ Finding next track...';
    await replenishSmartQueue(true);

    while (smartAutoplayQueue.length > 0) {
      const next = smartAutoplayQueue.shift();
      if (!next.unplayable && !deadTracksSet.has(next.id)) {
        playTrackImmediately(next);
        replenishSmartQueue();
        return;
      }
    }

    // 3. Fallback: Liked Songs or current list
    for (const cand of state.likedSongs) {
      if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
        cand.reason = 'From your Liked Songs';
        playTrackImmediately(cand);
        replenishSmartQueue();
        return;
      }
    }

    if (state.currentList.length > 0) {
      for (const cand of state.currentList) {
        if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
          playTrackImmediately(cand);
          replenishSmartQueue();
          return;
        }
      }
    }
  }

  function playTrackImmediately(track) {
    if (!track || !track.id) return;
    if (deadTracksSet.has(track.id) || track.unplayable) {
      console.warn(`Refusing to play unplayable track: ${track.title}`);
      handleDeckPlaybackError(track);
      return;
    }

    // If the requested track was already preloaded on standbyDeck, execute instant deck swap!
    if (preloadedTrack && preloadedTrack.id === track.id && isStandbyReady) {
      executeDeckSwapAndPlay(track);
      return;
    }

    preloadedTrack = null;
    isStandbyReady = false;
    state.currentTrack = track;
    currentTrackLogged = false;
    stallCounter = 0;
    lastAudioPosition = 0;

    if (track.id) {
      recentPlayedIds = [track.id, ...recentPlayedIds.filter(id => id !== track.id)].slice(0, 50);
    }
    if (track.title) {
      const songKey = getSongTitleKey(track.title, track.artist);
      if (songKey) recentPlayedTitleKeys.add(songKey);
    }

    updateNowPlayingMeta(track);

    const streamUrl = `/api/stream?id=${encodeURIComponent(track.id)}&title=${encodeURIComponent(track.title || '')}&artist=${encodeURIComponent(track.artist || '')}`;
    elements.pipelineStatus.textContent = track.reason ? `✨ ${track.reason}` : 'Streaming direct...';
    elements.engineBadge.textContent = 'Streaming';

    currentDeck.src = streamUrl;
    currentDeck.volume = sliderToPerceptualVolume(state.volume);

    // Immediately trigger pre-buffering of the next track while current track buffers/plays
    replenishSmartQueue().then(() => ensureNextTrackPreloaded());

    currentDeck.play().then(() => {
      state.isPlaying = true;
      updatePlayPauseButton();
      if (track.reason) {
        elements.pipelineStatus.textContent = `✨ ${track.reason}`;
      } else {
        elements.pipelineStatus.textContent = track.source === 'spotify' ? 'Spotify Direct' : 'YouTube Direct';
      }
      elements.equalizerVisualizer.style.display = 'flex';
      // Preload next track as soon as playback commences!
      ensureNextTrackPreloaded();
    }).catch(err => {
      console.warn('Playback start error:', err);
      handleDeckPlaybackError(track);
    });

    updateMediaSession(track);
  }

  function updateNowPlayingMeta(track) {
    elements.trackCover.src = track.thumbnail || 'https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=100&q=80';
    elements.trackName.textContent = track.title || 'Unknown Title';
    elements.trackArtist.textContent = track.artist || 'Unknown Artist';
    elements.trackSourceTag.textContent = track.source === 'spotify' ? 'SP' : 'YT';
    elements.trackSourceTag.style.color = track.source === 'spotify' ? 'var(--accent-sp)' : 'var(--accent-yt)';

    updateNowPlayingLikeBtn();

    // Update active row visual in current list
    const rows = elements.trackListContainer.querySelectorAll('.track-row');
    rows.forEach(r => {
      if (r.getAttribute('data-id') === track.id) {
        r.classList.add('now-playing');
      } else {
        r.classList.remove('now-playing');
      }
    });
  }

  function togglePlayPause() {
    if (!state.currentTrack) {
      if (state.currentList.length > 0) {
        playTrackImmediately(state.currentList[0]);
      }
      return;
    }

    if (elements.audioEngine.paused) {
      elements.audioEngine.play();
      state.isPlaying = true;
      elements.equalizerVisualizer.style.display = 'flex';
    } else {
      elements.audioEngine.pause();
      state.isPlaying = false;
      elements.equalizerVisualizer.style.display = 'none';
    }
    updatePlayPauseButton();
  }

  function updatePlayPauseButton() {
    if (state.isPlaying) {
      elements.playIcon.style.display = 'none';
      elements.pauseIcon.style.display = 'block';
    } else {
      elements.playIcon.style.display = 'block';
      elements.pauseIcon.style.display = 'none';
    }
  }

  function playNextTrack() {
    const currentKey = state.currentTrack ? getSongTitleKey(state.currentTrack.title, state.currentTrack.artist) : '';

    // 1. If we have preloaded and verified the upcoming track on standbyDeck, swap INSTANTLY (0ms gapless transition!)
    if (preloadedTrack && isStandbyReady && !preloadedTrack.unplayable && !deadTracksSet.has(preloadedTrack.id)) {
      if (!currentKey || !isDuplicateSongTitle(preloadedTrack.title, preloadedTrack.artist, [currentKey])) {
        const next = preloadedTrack;
        if (state.queue.length > 0 && state.queue[0].id === next.id) {
          state.queue.shift();
          updateQueueUI();
        } else if (smartAutoplayQueue.length > 0 && smartAutoplayQueue[0].id === next.id) {
          smartAutoplayQueue.shift();
        }
        executeDeckSwapAndPlay(next);
        return;
      } else {
        preloadedTrack = null;
        isStandbyReady = false;
      }
    }

    // 2. If queue has items, consume from user manual queue (skipping unplayable)
    while (state.queue.length > 0) {
      let nextTrack;
      if (state.isShuffling) {
        const idx = Math.floor(Math.random() * state.queue.length);
        [nextTrack] = state.queue.splice(idx, 1);
      } else {
        nextTrack = state.queue.shift();
      }
      updateQueueUI();
      if (!nextTrack.unplayable && !deadTracksSet.has(nextTrack.id)) {
        playTrackImmediately(nextTrack);
        return;
      }
    }

    // 3. If user is playing inside a custom playlist or Liked Songs, advance to next verified playable track
    if (state.activeTab !== 'discover' && state.activeTab !== 'queue' && state.currentList.length > 0) {
      let curIdx = state.currentList.findIndex(t => t.id === state.currentTrack?.id);
      if (curIdx !== -1) {
        for (let i = curIdx + 1; i < state.currentList.length; i++) {
          const cand = state.currentList[i];
          if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
            playTrackImmediately(cand);
            return;
          }
        }
      }
      if (state.isLooping && state.currentList.length > 0) {
        for (let i = 0; i < state.currentList.length; i++) {
          const cand = state.currentList[i];
          if (!cand.unplayable && !deadTracksSet.has(cand.id)) {
            playTrackImmediately(cand);
            return;
          }
        }
      }
      // When playlist reaches the end or has no remaining playable tracks, smoothly transition into Smart Radio autoplay!
    }

    // 4. Intelligent Autoplay: play similar/recommended song tailored to taste profile
    triggerSmartAutoplay();
  }

  function playPrevTrack() {
    if (currentDeck.currentTime > 3) {
      currentDeck.currentTime = 0;
      return;
    }

    if (state.currentList.length > 0) {
      let curIdx = state.currentList.findIndex(t => t.id === state.currentTrack?.id);
      let prevIdx = (curIdx - 1 + state.currentList.length) % state.currentList.length;
      playTrackImmediately(state.currentList[prevIdx]);
    }
  }

  // Perceptual exponential volume curve (gamma = 2.2)
  // Maps linear 0-100 slider into perceptual human hearing curve
  // Prevents jumping to loud volumes at low slider values and spreads volume control evenly
  function sliderToPerceptualVolume(val) {
    const norm = Math.max(0, Math.min(100, val)) / 100.0;
    return Math.pow(norm, 2.2);
  }

  function setVolume(val) {
    state.volume = Math.max(0, Math.min(100, val));
    const gain = sliderToPerceptualVolume(state.volume);
    deckA.volume = gain;
    deckB.volume = gain;
    elements.volumeBar.value = state.volume;

    if (state.volume === 0) {
      state.isMuted = true;
    } else {
      state.isMuted = false;
    }
  }

  function toggleMute() {
    if (state.isMuted) {
      state.isMuted = false;
      setVolume(state.previousVolume || 80);
    } else {
      state.previousVolume = state.volume;
      state.isMuted = true;
      setVolume(0);
    }
  }

  // Windows Media Overlay Integration (MediaSession API)
  function updateMediaSession(track) {
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: track.title,
        artist: track.artist,
        album: 'Lightning Music',
        artwork: [
          { src: track.thumbnail, sizes: '512x512', type: 'image/jpeg' }
        ]
      });

      navigator.mediaSession.setActionHandler('play', () => togglePlayPause());
      navigator.mediaSession.setActionHandler('pause', () => togglePlayPause());
      navigator.mediaSession.setActionHandler('previoustrack', () => playPrevTrack());
      navigator.mediaSession.setActionHandler('nexttrack', () => playNextTrack());
      navigator.mediaSession.setActionHandler('seekto', (details) => {
        if (details.seekTime && elements.audioEngine.duration) {
          elements.audioEngine.currentTime = details.seekTime;
        }
      });
    }
  }

  // Audio Engine Event Listeners (Dual-Deck Setup)
  function initAudioEngineEvents() {
    function setupDeck(deck) {
      deck.addEventListener('play', () => {
        if (deck !== currentDeck) return;
        state.isPlaying = true;
        updatePlayPauseButton();
        elements.equalizerVisualizer.style.display = 'flex';
        elements.pipelineStatus.textContent = 'Playing';
      });

      deck.addEventListener('pause', () => {
        if (deck !== currentDeck) return;
        state.isPlaying = false;
        updatePlayPauseButton();
        elements.equalizerVisualizer.style.display = 'none';
        elements.pipelineStatus.textContent = 'Paused';
      });

      deck.addEventListener('waiting', () => {
        if (deck !== currentDeck) return;
        elements.pipelineStatus.textContent = 'Buffering...';
      });

      deck.addEventListener('playing', () => {
        if (deck !== currentDeck) return;
        elements.pipelineStatus.textContent = 'Playing';
      });

      deck.addEventListener('timeupdate', () => {
        if (deck !== currentDeck || state.isScrubbing) return;
        const cur = deck.currentTime || 0;
        const dur = deck.duration || 0;

        // Smart taste logging after 10 seconds of listening
        if (cur >= 10 && !currentTrackLogged && state.currentTrack) {
          currentTrackLogged = true;
          logTrackPlay(state.currentTrack);
        }

        // Proactively preload upcoming track as soon as current track plays (at >= 15% or 20s)
        if (dur > 0 && (cur / dur >= 0.15 || cur >= 20)) {
          ensureNextTrackPreloaded();
        }

        elements.currentTimeLabel.textContent = formatTime(cur);
        if (dur > 0) {
          elements.totalTimeLabel.textContent = formatTime(dur);
          elements.progressBar.value = (cur / dur) * 100;
        }
      });

      deck.addEventListener('ended', () => {
        if (deck !== currentDeck) return;
        if (state.isLooping && state.currentTrack) {
          deck.currentTime = 0;
          deck.play().catch(() => {});
        } else {
          playNextTrack();
        }
      });

      deck.addEventListener('error', (e) => {
        if (deck !== currentDeck) return;
        handleDeckPlaybackError(state.currentTrack);
      });
    }

    setupDeck(deckA);
    setupDeck(deckB);

    // Active Watchdog to prevent music stopping on long sessions
    if (playbackWatchdogTimer) clearInterval(playbackWatchdogTimer);
    playbackWatchdogTimer = setInterval(() => {
      if (!state.isPlaying || state.isScrubbing || !state.currentTrack) return;
      const cur = currentDeck.currentTime || 0;
      const dur = currentDeck.duration || 0;

      // 1. End-of-track freeze detection: Audio within 0.8s of end without 'ended' event firing
      if (dur > 3 && cur >= dur - 0.8) {
        playNextTrack();
        return;
      }

      // 2. Buffer freeze / stall detection: Playing state but position stuck for > 8s
      if (!currentDeck.paused && Math.abs(cur - lastAudioPosition) < 0.05) {
        stallCounter++;
        if (stallCounter === 4) {
          try { currentDeck.currentTime += 0.2; currentDeck.play().catch(() => {}); } catch (_) {}
        } else if (stallCounter >= 8) {
          stallCounter = 0;
          playNextTrack();
        }
      } else {
        stallCounter = 0;
      }
      lastAudioPosition = cur;
    }, 1000);
  }

  // Setup Global Keyboard & UI Event Listeners
  function initEventListeners() {
    initAudioEngineEvents();

    // Source Picker Buttons beside search bar
    elements.sourceBtnYouTube.addEventListener('click', () => setSource('youtube'));
    elements.sourceBtnSpotify.addEventListener('click', () => setSource('spotify'));

    // Search events
    elements.searchSubmitBtn.addEventListener('click', () => {
      executeSearch(elements.searchInput.value.trim());
    });

    elements.searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        executeSearch(elements.searchInput.value.trim());
      }
    });

    elements.searchInput.addEventListener('input', () => {
      elements.searchClearBtn.style.display = elements.searchInput.value ? 'block' : 'none';
    });

    elements.searchClearBtn.addEventListener('click', () => {
      elements.searchInput.value = '';
      elements.searchClearBtn.style.display = 'none';
      loadPopularTracks();
    });

    // Navigation Tab Switching
    elements.navItems.forEach(item => {
      item.addEventListener('click', () => {
        switchTab(item.dataset.tab);
      });
    });

    elements.clearQueueBtn.addEventListener('click', clearQueue);

    // Play All from Playlist / Liked Songs
    if (elements.playlistPlayAllBtn) {
      elements.playlistPlayAllBtn.addEventListener('click', handlePlayAll);
    }

    // Delete Current Custom Playlist
    if (elements.deletePlaylistBtn) {
      elements.deletePlaylistBtn.addEventListener('click', () => {
        if (state.activeTab && state.activeTab.startsWith('pl_')) {
          const pl = state.playlists.find(p => p.id === state.activeTab);
          if (pl && confirm(`Delete playlist "${pl.name}"?`)) {
            deletePlaylist(pl.id);
          }
        }
      });
    }

    // Now Playing Like Button
    if (elements.nowPlayingLikeBtn) {
      elements.nowPlayingLikeBtn.addEventListener('click', () => {
        if (state.currentTrack) {
          toggleLikeTrack(state.currentTrack);
        }
      });
    }

    // Sidebar Create Playlist Button
    if (elements.sidebarCreatePlaylistBtn) {
      elements.sidebarCreatePlaylistBtn.addEventListener('click', openCreatePlaylistModal);
    }

    // Create Playlist Modal Controls
    if (elements.closeCreatePlaylistModal) {
      elements.closeCreatePlaylistModal.addEventListener('click', closeCreatePlaylistModal);
    }
    if (elements.cancelCreatePlaylistBtn) {
      elements.cancelCreatePlaylistBtn.addEventListener('click', closeCreatePlaylistModal);
    }
    if (elements.confirmCreatePlaylistBtn) {
      elements.confirmCreatePlaylistBtn.addEventListener('click', handleConfirmCreatePlaylist);
    }
    if (elements.playlistNameInput) {
      elements.playlistNameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleConfirmCreatePlaylist();
        if (e.key === 'Escape') closeCreatePlaylistModal();
      });
    }

    // Add To Playlist Modal Controls
    if (elements.closeAddToPlaylistModal) {
      elements.closeAddToPlaylistModal.addEventListener('click', closeAddToPlaylistModal);
    }
    if (elements.modalDoneBtn) {
      elements.modalDoneBtn.addEventListener('click', closeAddToPlaylistModal);
    }
    if (elements.modalNewPlaylistBtn) {
      elements.modalNewPlaylistBtn.addEventListener('click', () => {
        closeAddToPlaylistModal();
        openCreatePlaylistModal();
      });
    }

    // Custom In-App Window Controls
    if (elements.winMinBtn) {
      elements.winMinBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fetch('/api/window/minimize', { method: 'POST' }).catch(() => {});
      });
    }

    if (elements.winMaxBtn) {
      elements.winMaxBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fetch('/api/window/maximize', { method: 'POST' }).catch(() => {});
      });
    }

    if (elements.winCloseBtn) {
      elements.winCloseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fetch('/api/window/close', { method: 'POST' }).catch(() => {});
      });
    }

    // Top Header Dragging
    if (elements.topNav) {
      elements.topNav.addEventListener('mousedown', (e) => {
        if (e.target.closest('button, input, .search-wrapper, .window-controls')) return;
        fetch('/api/window/drag', { method: 'POST' }).catch(() => {});
      });
    }

    // Player Controls
    elements.playPauseBtn.addEventListener('click', togglePlayPause);
    elements.nextBtn.addEventListener('click', playNextTrack);
    elements.prevBtn.addEventListener('click', playPrevTrack);

    elements.shuffleBtn.addEventListener('click', () => {
      state.isShuffling = !state.isShuffling;
      elements.shuffleBtn.classList.toggle('active', state.isShuffling);
    });

    elements.loopBtn.addEventListener('click', () => {
      state.isLooping = !state.isLooping;
      elements.loopBtn.classList.toggle('active', state.isLooping);
    });

    // Scrubber
    elements.progressBar.addEventListener('mousedown', () => { state.isScrubbing = true; });
    elements.progressBar.addEventListener('touchstart', () => { state.isScrubbing = true; });

    elements.progressBar.addEventListener('input', (e) => {
      const dur = elements.audioEngine.duration || 0;
      if (dur > 0) {
        const target = (parseFloat(e.target.value) / 100) * dur;
        elements.currentTimeLabel.textContent = formatTime(target);
      }
    });

    elements.progressBar.addEventListener('change', (e) => {
      const dur = elements.audioEngine.duration || 0;
      if (dur > 0) {
        const target = (parseFloat(e.target.value) / 100) * dur;
        elements.audioEngine.currentTime = target;
      }
      state.isScrubbing = false;
    });

    // Volume
    elements.volumeBar.addEventListener('input', (e) => {
      setVolume(parseInt(e.target.value, 10));
    });

    elements.muteBtn.addEventListener('click', toggleMute);
  }

  // Modal & Playlist Action Handlers
  function openCreatePlaylistModal() {
    if (!elements.createPlaylistModal) return;
    elements.createPlaylistModal.style.display = 'flex';
    elements.playlistNameInput.value = '';
    setTimeout(() => elements.playlistNameInput.focus(), 50);
  }

  function closeCreatePlaylistModal() {
    if (!elements.createPlaylistModal) return;
    elements.createPlaylistModal.style.display = 'none';
    elements.playlistNameInput.value = '';
  }

  function handleConfirmCreatePlaylist() {
    const name = elements.playlistNameInput.value.trim();
    if (!name) return;
    const pl = createPlaylist(name);
    closeCreatePlaylistModal();
    if (pl) {
      // If we opened this while trying to add a track, add it to the newly created playlist!
      if (state.modalTargetTrack) {
        addTrackToPlaylist(pl.id, state.modalTargetTrack);
      }
      switchTab(pl.id);
    }
  }

  function openAddToPlaylistModal(track) {
    if (!elements.addToPlaylistModal || !track) return;
    state.modalTargetTrack = track;

    // Render Track Preview
    elements.modalTargetTrackSummary.innerHTML = `
      <img src="${track.thumbnail || 'https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=100&q=80'}" alt="Cover">
      <div class="target-track-info">
        <div class="target-track-title">${track.title}</div>
        <div class="target-track-artist">${track.artist} • <span style="color: ${track.source === 'spotify' ? 'var(--accent-sp)' : 'var(--accent-yt)'}">${track.source.toUpperCase()}</span></div>
      </div>
    `;

    renderModalPlaylistOptions();
    elements.addToPlaylistModal.style.display = 'flex';
  }

  function closeAddToPlaylistModal() {
    if (!elements.addToPlaylistModal) return;
    elements.addToPlaylistModal.style.display = 'none';
    state.modalTargetTrack = null;
  }

  function renderModalPlaylistOptions() {
    if (!elements.modalPlaylistSelectList || !state.modalTargetTrack) return;
    elements.modalPlaylistSelectList.innerHTML = '';

    const track = state.modalTargetTrack;

    // 1. Liked Songs Row
    const isLiked = isTrackLiked(track.id);
    const likedRow = document.createElement('div');
    likedRow.className = `playlist-select-row ${isLiked ? 'in-playlist' : ''}`;
    likedRow.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="color: #ec4899; font-size: 1.1rem;">♥</span>
        <span class="playlist-select-name">Liked Songs</span>
      </div>
      <span class="playlist-select-status">${isLiked ? '✓ Saved' : '+ Save'}</span>
    `;
    likedRow.addEventListener('click', () => {
      toggleLikeTrack(track);
      renderModalPlaylistOptions();
    });
    elements.modalPlaylistSelectList.appendChild(likedRow);

    // 2. Custom Playlists
    if (state.playlists.length === 0) {
      const emptyNotice = document.createElement('div');
      emptyNotice.style.cssText = 'font-size: 0.8rem; color: var(--text-dim); padding: 8px 0; font-style: italic;';
      emptyNotice.textContent = 'No custom playlists yet. Click "+ Create New Playlist" below.';
      elements.modalPlaylistSelectList.appendChild(emptyNotice);
      return;
    }

    state.playlists.forEach(pl => {
      const inPl = pl.tracks && pl.tracks.some(t => t.id === track.id);
      const row = document.createElement('div');
      row.className = `playlist-select-row ${inPl ? 'in-playlist' : ''}`;
      row.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="color: var(--accent-cyan); font-size: 0.9rem;">♫</span>
          <span class="playlist-select-name">${pl.name}</span>
        </div>
        <span class="playlist-select-status">${inPl ? '✓ Added' : '+ Add'}</span>
      `;
      row.addEventListener('click', () => {
        toggleTrackInPlaylist(pl.id, track);
        renderModalPlaylistOptions();
        // If currently on this playlist tab, re-render
        if (state.activeTab === pl.id) {
          renderTrackList(pl.tracks, false, false, pl.id);
        }
      });
      elements.modalPlaylistSelectList.appendChild(row);
    });
  }

  function handlePlayAll() {
    let list = [];
    if (state.activeTab === 'liked') {
      list = state.likedSongs;
    } else if (state.activeTab && state.activeTab.startsWith('pl_')) {
      const pl = state.playlists.find(p => p.id === state.activeTab);
      if (pl) list = pl.tracks;
    }

    if (!list || list.length === 0) return;

    // Load full list into queue and play track 0
    state.queue = [...list];
    updateQueueUI();
    playTrackImmediately(list[0]);
  }

  // Boot Application
  function init() {
    loadSavedData();
    initEventListeners();
    setVolume(state.volume);
    loadPopularTracks();

    // Slider fill via --pct CSS custom property
    function updateSliderFill(slider) {
      if (!slider) return;
      const pct = ((slider.value - slider.min) / (slider.max - slider.min)) * 100;
      slider.style.setProperty('--pct', pct + '%');
    }
    const progressBarEl = document.getElementById('progressBar');
    const volumeBarEl = document.getElementById('volumeBar');
    if (progressBarEl) {
      progressBarEl.addEventListener('input', (e) => updateSliderFill(e.target));
      updateSliderFill(progressBarEl);
    }
    if (volumeBarEl) {
      volumeBarEl.addEventListener('input', (e) => updateSliderFill(e.target));
      updateSliderFill(volumeBarEl);
    }

    // Heartbeat to keep backend server alive while app window is open
    setInterval(() => {
      fetch('/api/heartbeat').catch(() => {});
    }, 2000);

    // Auto-Updater Check and Interactive Banner
    const updateBanner = document.getElementById('updateBanner');
    const updateBannerTitle = document.getElementById('updateBannerTitle');
    const updateBannerSub = document.getElementById('updateBannerSub');
    const updateDismissBtn = document.getElementById('updateDismissBtn');
    const updateApplyBtn = document.getElementById('updateApplyBtn');
    const updateProgressWrap = document.getElementById('updateProgressWrap');
    const updateProgressBar = document.getElementById('updateProgressBar');

    let isUpdating = false;

    async function pollUpdateStatus() {
      if (isUpdating) return;
      try {
        const res = await fetch('/api/update_status');
        const data = await res.json();
        if (data.update_available && !data.downloading) {
          updateBannerTitle.textContent = `⚡ Update v${data.latest_version} Available!`;
          updateBannerSub.textContent = data.changelog ? (data.changelog.slice(0, 75) + '...') : 'A new update is ready to install.';
          updateBanner.style.display = 'flex';
        }
      } catch (e) {}
    }

    if (updateDismissBtn) {
      updateDismissBtn.addEventListener('click', () => {
        updateBanner.style.display = 'none';
      });
    }

    if (updateApplyBtn) {
      updateApplyBtn.addEventListener('click', async () => {
        isUpdating = true;
        updateApplyBtn.disabled = true;
        updateDismissBtn.style.display = 'none';
        updateApplyBtn.textContent = 'Updating...';
        updateProgressWrap.style.display = 'block';

        try {
          await fetch('/api/trigger_update');
          const progressInterval = setInterval(async () => {
            try {
              const res = await fetch('/api/update_status');
              const data = await res.json();
              if (data.downloading) {
                updateProgressBar.style.width = `${data.progress || 0}%`;
                updateBannerSub.textContent = `Downloading update... ${data.progress}%`;
              } else if (data.ready_to_restart) {
                clearInterval(progressInterval);
                updateProgressBar.style.width = '100%';
                updateBannerTitle.textContent = '⚡ Restarting...';
                updateBannerSub.textContent = 'Applying updates and reopening Lightning Player!';
              } else if (data.error) {
                clearInterval(progressInterval);
                isUpdating = false;
                updateApplyBtn.disabled = false;
                updateDismissBtn.style.display = 'inline-block';
                updateApplyBtn.textContent = 'Retry';
                updateBannerSub.textContent = `Update failed: ${data.error}`;
              }
            } catch (err) {}
          }, 400);
        } catch (e) {
          isUpdating = false;
          updateApplyBtn.disabled = false;
          updateDismissBtn.style.display = 'inline-block';
          updateApplyBtn.textContent = 'Retry';
        }
      });
    }

    // Check updates 3s after boot, then every 10 minutes
    setTimeout(pollUpdateStatus, 3000);
    setInterval(pollUpdateStatus, 600000);

    // Send shutdown beacon when window is closed
    window.addEventListener('beforeunload', () => {
      try {
        navigator.sendBeacon('/api/shutdown');
      } catch (e) {}
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
