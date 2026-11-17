/* One implementation of hot-list lookup and eviction for all scanner consumers. MIT */
#include "xscan_hot.h"

xs_hot_t *xs_hot_near(xs_hot_t *hot, unsigned capacity, uint32_t hz, uint32_t tolerance, int up) {
  unsigned i;
  for (i = 0; i < capacity; ++i) {
    xs_hot_t *h = &hot[i];
    if (h->hz && (!up || h->up) &&
        (h->hz > hz ? h->hz - hz : hz - h->hz) <= tolerance) return h;
  }
  return 0;
}

xs_hot_t *xs_hot_slot(xs_hot_t *hot, unsigned capacity, int level, unsigned hit_db) {
  xs_hot_t *oldest = 0, *weakest = 0;
  unsigned i;
  unsigned encoded = level < -174 ? 0u : level > 81 ? 255u : (unsigned)(level + 174);
  for (i = 0; i < capacity; ++i) {
    xs_hot_t *h = &hot[i];
    if (!h->hz) return h;
    if (!h->up && !h->spur && (!oldest || h->last < oldest->last)) oldest = h;
    if (!weakest || h->lvl < weakest->lvl) weakest = h;
  }
  return oldest ? oldest : (weakest && encoded >= (unsigned)weakest->lvl + hit_db ? weakest : 0);
}
