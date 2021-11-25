import { chakra, Box, Icon, Tooltip, Divider, Heading } from '@chakra-ui/react'
import React from 'react'

import { usePlayer, usePlayerRegionIfPlaying, formatDuration } from './player'
import { useTranslation } from 'react-i18next'
import { FaVolumeUp } from 'react-icons/fa'
import { MdNextWeek } from 'react-icons/md'

export function PostTranscriptSection (props) {
  const { post } = props
  const { t } = useTranslation()
  if (!hasTranscript(post)) return null
  // const [show, setShow] = React.useState(false)
  return (
    <Box p='4' border='1px' borderColor='gray.200' bg='white' borderRadius='sm'>
      <Heading size='md' mb='4'>{t('transcript.title', 'Transcript')}</Heading>
      <PostTranscript post={post} />
    </Box>
  )
}

export function PostTranscript (props) {
  const { post } = props
  let medias = post.media
  if (!medias) return null
  medias = medias.filter(media => media.transcript)
  if (!medias.length) return null

  return (
    <>
      {medias.map((media, i) => (
        <MediaTranscript
          key={i}
          media={media}
          post={post}
          delta={i}
        />
      ))}
    </>
  )
}

const styleInjected = false

export function MediaTranscript (props) {
  const { media, post, delta } = props
  const parts = media.transcript.parts
  const { setTrack, setMark, setPost } = usePlayer()

  const words = React.useMemo(() => (
    <Box>
      {parts.map((word, i) => {
        // Hue 0 = red, hue 100 = green
        const conf = word.conf
        const exp = 5
        const hue = (Math.pow(conf, exp)) * 100
        const color = `hsl(${hue}, 100%, 90%)`
        const style = {
          background: color
        }
        return (
          <span key={i} value={[word.word, word.start, word.end]} style={style} onClick={onClick} onMouseUp={handleMouseUp.bind(word)}>
            {word.word}&nbsp;
          </span>
        )
        function onClick (e) {
          setPost(post)
          setTrack(media)
          setMark(word)
        }
      })}
    </Box>
  ), [parts])

  function handleMouseUp () {
    const selection = document.getSelection()
    const range = document.createRange()
    range.setStart(selection.anchorNode, selection.anchorOffset)
    range.setEnd(selection.focusNode, selection.focusOffset)
    range.detach()

    const endNode = selection.focusNode
    const startNode = selection.anchorNode
    const endOffset = selection.focusOffset
    const backwards = range.collapsed
    selection.collapse(selection.anchorNode, selection.anchorOffset)
    let direction = []

    if (backwards) {
      direction = ['backward', 'forward']
    } else {
      direction = ['forward', 'backward']
    }
    selection.modify('move', direction[0], 'character')
    selection.modify('move', direction[1], 'word')
    selection.extend(endNode, endOffset)
    selection.modify('extend', direction[1], 'character')
    selection.modify('extend', direction[0], 'word')
    let start = startNode.parentNode.attributes.value.nodeValue.split(',')
    let end = endNode.parentNode.attributes.value.nodeValue.split(',')
    console.log('Start: ', start[1], ' End: ', end[1])
    if (start[1] > end[1]) {
      const temp = start
      start = end
      end = temp
    }
    console.log('Start: ', start[1], ' End: ', end[2])
  }

  // TODO: Don't do this like this.
  let globalStyle = null
  if (!styleInjected) {
    globalStyle = (
      <style>
        {`.transcript-container > span {
          border-radius: 5px;
          border: 1px solid transparent;
          padding: 0;
          margin-right: 2px;
          display: inline-block;
          cursor: pointer;
        }
        .transcript-container > span:hover {
          border-color: rgba(0,0,0,0.4);
        }`}
      </style>
    )
  }

  return (
    <Box className='transcript-container'>
      {globalStyle}
      {words}
    </Box>
  )

  function onClick (mark, _e) {
    // setDidPlay(false)
    setTrack(media)
    setPost(post)
    setMark(mark)
  }
}

export function TranscriptSnippet (props) {
  const { post, snippet } = props

  const { setTrack, setMark, setPost } = usePlayer()

  const [didPlay, setDidPlay] = React.useState(false)

  const mark = React.useMemo(() => {
    return parseTranscriptSentence(snippet)
  }, [snippet])

  const { id, start, end, sentence, words } = mark

  const track = post.media[Number(mark.id)]

  const style = {
    display: 'inline-block',
    border: '1px solid #eee',
    padding: '2px 10px',
    margin: '5px 5px 0 5px',
    cursor: 'pointer',
    borderRadius: '10px'
  }

  const renderedWords = React.useMemo(() => (
    <>
      {words.map((word, i) => <TranscriptWord key={i} {...word} post={post} />)}
    </>
  ), [words])

  return (
    <Tooltip label='Click to play'>
      <Box onClick={onClick} style={style} _hover={{ bg: 'gray.50' }} position='relative'>
        {renderedWords}
        <Icon as={FaVolumeUp} ml='2' mr='2' color='gray.400' />
        <chakra.span fontSize='sm' color='gray.600'>{formatDuration(mark.start)}</chakra.span>
        <TranscriptPlayingOverlay track={track} mark={mark} />
      </Box>
    </Tooltip>
  )

  function onClick (e) {
    setDidPlay(false)
    setTrack(track)
    setPost(post)
    setMark(mark)
  }
}

function TranscriptPlayingOverlay (props) {
  const { track, mark } = props
  const currentTimeIfPlaying = usePlayerRegionIfPlaying({ track, mark })
  const [hasPlayed, setHasPlayed] = React.useState(false)
  const percentPlaying = React.useMemo(() => {
    if (!hasPlayed && currentTimeIfPlaying) setHasPlayed(true)
    if (!currentTimeIfPlaying) return hasPlayed ? 1 : 0
    const percent = (currentTimeIfPlaying - mark.start) / (mark.end - mark.start)
    return percent
  }, [mark, currentTimeIfPlaying])

  const overlayStyle = {
    position: 'absolute',
    left: '0px',
    top: '0px',
    bottom: '0px',
    backgroundColor: 'rgba(0, 0, 0, 0.05)',
    zIndex: 10,
    width: (percentPlaying * 100) + '%'
    // transition: 'width linear .5s'
  }
  return (
    <div style={overlayStyle} />
  )
}

export function TranscriptWord (props) {
  const { highlightWord, playOnClick, track, post, word, start, end, conf, id, onClick, style } = props
  const { setTrack, setPost, setMark } = usePlayer()
  const alpha = Number(conf)

  const DEFAULT_STYLE = {
    display: 'inline-block',
    cursor: 'pointer',
    color: `rgba(0,0,0,${alpha})`
  }

  let bg = 'transparent'
  if (highlightWord) bg = 'highlightMark'

  const inner = (
    <>
      <Box
        as='span'
        bg={bg}
        style={style || DEFAULT_STYLE}
        onClick={onWordClick}
      >
        {word}
      </Box>
      &nbsp;
    </>
  )

  if (playOnClick) {
    return (
      <Tooltip label='Click to play'>{inner}</Tooltip>
    )
  }

  return inner

  function onWordClick (e) {
    const mark = { word, start, end, conf, id }
    if (onClick) onClick(mark, e)
    if (playOnClick) {
      if (track) setTrack(track)
      if (post) setPost(post)
      setMark(mark)
    }
  }
}

function hasTranscript (post) {
  if (!post || !post.media || !post.media.length) return false
  return post.media.filter(m => m.transcript).length > 0
}

export function parseTranscriptSentence (value) {
  const words = parseTranscriptWords(value)
  const firstMeta = words.filter(word => word.start !== undefined && word.end !== undefined)[0]
  const { id, start } = firstMeta
  const lastMeta = [...words].reverse().filter(word => word.end !== undefined)[0]
  const { end } = lastMeta
  const sentence = words.map(word => word.word).join(' ')
  return { id, start, end, sentence, words }
}

export function parseTranscriptWords (value) {
  const tokens = value.split(' ')
  return tokens.map((token) => {
    let highlightWord = false
    if (token.startsWith('<mark>')) {
      highlightWord = true
    }
    token = token.replace('<mark>', '')
    token = token.replace('</mark>', '')
    const [word, meta] = token.split('|')
    // skip words that are actually a meta string
    if (word.indexOf(':') !== -1) return null
    const item = { word, highlightWord }
    if (meta) {
      const [start, end, conf, id] = meta.split(':')
      return { ...item, start, end, conf, id }
    } else {
      return item
    }
  }).filter(x => x)
}
