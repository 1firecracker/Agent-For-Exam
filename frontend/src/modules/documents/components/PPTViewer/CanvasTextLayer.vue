<template>
  <div class="canvas-text-layer" :style="layerStyle">
    <div
      v-for="(item, index) in items"
      :key="index"
      class="text-item"
      :style="getItemStyle(item)"
    >
      {{ item.str }}
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  width: {
    type: Number,
    default: 0
  },
  height: {
    type: Number,
    default: 0
  }
})

const layerStyle = computed(() => ({
  position: 'absolute',
  top: 0,
  left: 0,
  width: props.width + 'px',
  height: props.height + 'px',
  pointerEvents: 'none'
}))

const getItemStyle = (item) => ({
  position: 'absolute',
  left: item.transform[4] + 'px',
  top: item.transform[5] + 'px',
  fontSize: item.fontSize + 'px'
})
</script>

<style scoped>
.canvas-text-layer {
  color: transparent;
}

.text-item {
  white-space: pre;
}
</style>


